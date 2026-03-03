"""Central safety supervisor node.

Monitors all safety inputs (obstacles, geofence, watchdog, e-stop),
publishes SafetyStatus, and can override cmd_vel to zero when a
safety condition is active. Implements a state machine:
SAFE -> WARNING -> CRITICAL -> ESTOP.
"""

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

from striper_msgs.msg import SafetyStatus

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


class SafetySupervisorNode(Node):
    """Central safety arbiter for the striper robot."""

    SAFE = SafetyStatus.SAFE
    WARNING = SafetyStatus.WARNING
    CRITICAL = SafetyStatus.CRITICAL
    ESTOP = SafetyStatus.ESTOP

    def __init__(self):
        super().__init__('safety_supervisor')

        # Parameters
        self.declare_parameter('estop_gpio_pin', 27)
        self.declare_parameter('estop_active_low', True)
        self.declare_parameter('publish_rate', 10.0)  # Hz
        self.declare_parameter('heartbeat_timeout', 2.0)  # seconds

        self._estop_pin = self.get_parameter('estop_gpio_pin').value
        self._estop_active_low = self.get_parameter('estop_active_low').value

        # Setup e-stop GPIO
        self._has_estop_gpio = False
        if _HAS_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                pull = GPIO.PUD_UP if self._estop_active_low else GPIO.PUD_DOWN
                GPIO.setup(self._estop_pin, GPIO.IN, pull_up_down=pull)
                self._has_estop_gpio = True
                self.get_logger().info(f'E-stop GPIO pin {self._estop_pin} configured')
            except Exception as e:
                self.get_logger().warn(f'E-stop GPIO setup failed: {e}')

        # Safety input state
        self._obstacle_detected = False
        self._obstacle_distance = float('inf')
        self._geofence_violation = False
        self._watchdog_timeout = False
        self._estop_active = False
        self._safety_level = self.SAFE

        # Subscribers
        self._obstacle_sub = self.create_subscription(
            Bool, 'safety/obstacle_detected', self._obstacle_cb, 10
        )
        self._geofence_sub = self.create_subscription(
            Bool, 'safety/geofence_violation', self._geofence_cb, 10
        )
        self._watchdog_sub = self.create_subscription(
            Bool, 'safety/watchdog_timeout', self._watchdog_cb, 10
        )

        # Cmd_vel input (from Nav2 or manual) and safety override output
        self._cmd_vel_sub = self.create_subscription(
            Twist, 'cmd_vel_nav', self._cmd_vel_cb, 10
        )
        self._cmd_vel_override_pub = self.create_publisher(
            Twist, 'safety/cmd_vel_override', 10
        )

        # Status publisher
        self._status_pub = self.create_publisher(SafetyStatus, 'safety_status', 10)

        # Main loop timer
        rate = self.get_parameter('publish_rate').value
        self._timer = self.create_timer(1.0 / rate, self._update)

        self._last_cmd_vel = Twist()

        self.get_logger().info('SafetySupervisor ready')

    def _obstacle_cb(self, msg: Bool):
        self._obstacle_detected = msg.data

    def _geofence_cb(self, msg: Bool):
        self._geofence_violation = msg.data

    def _watchdog_cb(self, msg: Bool):
        self._watchdog_timeout = msg.data

    def _cmd_vel_cb(self, msg: Twist):
        self._last_cmd_vel = msg

    def _read_estop_hardware(self) -> bool:
        """Read hardware e-stop pin state."""
        if not self._has_estop_gpio:
            return False
        try:
            pin_state = GPIO.input(self._estop_pin)
            if self._estop_active_low:
                return pin_state == GPIO.LOW
            else:
                return pin_state == GPIO.HIGH
        except Exception:
            return False

    def _update(self):
        """Main safety evaluation loop."""
        # Read hardware e-stop
        self._estop_active = self._read_estop_hardware()

        # Determine safety level (highest priority wins)
        if self._estop_active:
            self._safety_level = self.ESTOP
        elif self._geofence_violation or self._watchdog_timeout:
            self._safety_level = self.CRITICAL
        elif self._obstacle_detected:
            self._safety_level = self.WARNING
        else:
            self._safety_level = self.SAFE

        # Override cmd_vel based on safety level
        output_cmd = Twist()
        if self._safety_level >= self.CRITICAL:
            # Full stop
            output_cmd = Twist()  # All zeros
        elif self._safety_level == self.WARNING:
            # Allow reduced speed
            output_cmd = self._last_cmd_vel
            speed_factor = 0.3
            output_cmd.linear.x *= speed_factor
            output_cmd.linear.y *= speed_factor
            output_cmd.angular.z *= speed_factor
        else:
            # Pass through
            output_cmd = self._last_cmd_vel

        self._cmd_vel_override_pub.publish(output_cmd)

        # Publish safety status
        status = SafetyStatus()
        status.estop_active = self._estop_active
        status.obstacle_detected = self._obstacle_detected
        status.geofence_violation = self._geofence_violation
        status.obstacle_distance = self._obstacle_distance
        status.safety_level = self._safety_level
        status.status_message = self._level_name(self._safety_level)
        self._status_pub.publish(status)

    def _level_name(self, level: int) -> str:
        names = {
            self.SAFE: 'SAFE',
            self.WARNING: 'WARNING - obstacle detected',
            self.CRITICAL: 'CRITICAL - motion stopped',
            self.ESTOP: 'ESTOP - emergency stop active',
        }
        return names.get(level, 'UNKNOWN')

    def destroy_node(self):
        # Publish stop command
        self._cmd_vel_override_pub.publish(Twist())
        if self._has_estop_gpio:
            try:
                GPIO.cleanup(self._estop_pin)
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SafetySupervisorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
