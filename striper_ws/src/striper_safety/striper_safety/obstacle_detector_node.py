"""Ultrasonic obstacle detector node.

Reads HC-SR04 ultrasonic sensors via GPIO (trigger/echo), publishes
Range messages, and flags obstacle detections with warning and stop
zones. Includes moving average and outlier rejection filtering.
"""

import time
import collections

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Range
from std_msgs.msg import Bool, Float32

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


class UltrasonicSensor:
    """Single ultrasonic sensor driver with filtering."""

    SPEED_OF_SOUND = 343.0  # m/s at 20C

    def __init__(self, trigger_pin, echo_pin, name, window_size=5):
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.name = name
        self._readings = collections.deque(maxlen=window_size)
        self._last_valid = float('inf')

        if _HAS_GPIO:
            GPIO.setup(trigger_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(echo_pin, GPIO.IN)

    def read(self) -> float:
        """Read distance in meters. Returns inf on timeout."""
        if not _HAS_GPIO:
            return 5.0  # Mock: 5m (no obstacle)

        try:
            # Send trigger pulse
            GPIO.output(self.trigger_pin, GPIO.HIGH)
            time.sleep(0.00001)  # 10us pulse
            GPIO.output(self.trigger_pin, GPIO.LOW)

            # Wait for echo start (with timeout)
            timeout = time.monotonic() + 0.03  # 30ms max
            while GPIO.input(self.echo_pin) == GPIO.LOW:
                pulse_start = time.monotonic()
                if pulse_start > timeout:
                    return float('inf')

            # Wait for echo end
            while GPIO.input(self.echo_pin) == GPIO.HIGH:
                pulse_end = time.monotonic()
                if pulse_end > timeout:
                    return float('inf')

            # Calculate distance
            duration = pulse_end - pulse_start
            distance = (duration * self.SPEED_OF_SOUND) / 2.0

            return distance

        except Exception:
            return float('inf')

    def read_filtered(self) -> float:
        """Read with moving average and outlier rejection."""
        raw = self.read()

        if raw == float('inf') or raw < 0.02 or raw > 10.0:
            # Outlier: ignore readings outside valid range
            return self._last_valid

        self._readings.append(raw)

        if len(self._readings) < 2:
            self._last_valid = raw
            return raw

        # Outlier rejection: remove readings > 2 std devs from mean
        readings = list(self._readings)
        mean = sum(readings) / len(readings)
        variance = sum((r - mean) ** 2 for r in readings) / len(readings)
        std_dev = variance ** 0.5

        if std_dev > 0.001:
            filtered = [r for r in readings if abs(r - mean) < 2 * std_dev]
        else:
            filtered = readings

        if filtered:
            result = sum(filtered) / len(filtered)
        else:
            result = mean

        self._last_valid = result
        return result


class ObstacleDetectorNode(Node):
    """Ultrasonic obstacle detection with warning and stop zones."""

    def __init__(self):
        super().__init__('obstacle_detector')

        # Parameters
        self.declare_parameter('warning_distance', 2.0)  # meters
        self.declare_parameter('stop_distance', 0.5)      # meters
        self.declare_parameter('scan_rate', 10.0)          # Hz
        self.declare_parameter('filter_window', 5)

        # Sensor pins (front left and front right)
        self.declare_parameter('fl_trigger_pin', 5)
        self.declare_parameter('fl_echo_pin', 6)
        self.declare_parameter('fr_trigger_pin', 13)
        self.declare_parameter('fr_echo_pin', 19)

        self._warning_dist = self.get_parameter('warning_distance').value
        self._stop_dist = self.get_parameter('stop_distance').value
        window = self.get_parameter('filter_window').value

        # GPIO setup
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)

        # Create sensors
        self._sensors = [
            UltrasonicSensor(
                self.get_parameter('fl_trigger_pin').value,
                self.get_parameter('fl_echo_pin').value,
                'front_left',
                window,
            ),
            UltrasonicSensor(
                self.get_parameter('fr_trigger_pin').value,
                self.get_parameter('fr_echo_pin').value,
                'front_right',
                window,
            ),
        ]

        # Publishers
        self._range_pubs = {}
        for sensor in self._sensors:
            self._range_pubs[sensor.name] = self.create_publisher(
                Range, f'ultrasonic/{sensor.name}', 10
            )

        self._obstacle_pub = self.create_publisher(Bool, 'safety/obstacle_detected', 10)
        self._distance_pub = self.create_publisher(Float32, 'safety/obstacle_distance', 10)

        # Scan timer
        rate = self.get_parameter('scan_rate').value
        self._timer = self.create_timer(1.0 / rate, self._scan)

        self.get_logger().info(
            f'ObstacleDetector ready: warning={self._warning_dist}m, '
            f'stop={self._stop_dist}m'
        )

    def _scan(self):
        """Read all sensors and evaluate obstacle status."""
        min_distance = float('inf')

        for sensor in self._sensors:
            distance = sensor.read_filtered()

            # Publish Range message
            range_msg = Range()
            range_msg.header.stamp = self.get_clock().now().to_msg()
            range_msg.header.frame_id = f'{sensor.name}_link'
            range_msg.radiation_type = Range.ULTRASOUND
            range_msg.field_of_view = 0.26  # ~15 degrees
            range_msg.min_range = 0.02
            range_msg.max_range = 4.0
            range_msg.range = distance
            self._range_pubs[sensor.name].publish(range_msg)

            if distance < min_distance:
                min_distance = distance

        # Publish obstacle detection
        obstacle_detected = min_distance < self._warning_dist
        obstacle_msg = Bool()
        obstacle_msg.data = obstacle_detected
        self._obstacle_pub.publish(obstacle_msg)

        # Publish minimum distance
        dist_msg = Float32()
        dist_msg.data = min_distance if min_distance != float('inf') else -1.0
        self._distance_pub.publish(dist_msg)

        if min_distance < self._stop_dist:
            self.get_logger().warn(
                f'STOP ZONE: obstacle at {min_distance:.2f}m',
                throttle_duration_sec=1.0,
            )
        elif min_distance < self._warning_dist:
            self.get_logger().info(
                f'Warning zone: obstacle at {min_distance:.2f}m',
                throttle_duration_sec=2.0,
            )

    def destroy_node(self):
        if _HAS_GPIO:
            for sensor in self._sensors:
                try:
                    GPIO.cleanup(sensor.trigger_pin)
                    GPIO.cleanup(sensor.echo_pin)
                except Exception:
                    pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
