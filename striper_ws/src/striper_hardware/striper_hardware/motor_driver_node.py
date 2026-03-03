"""Motor driver node for ESP32 serial communication.

Receives cmd_vel, converts to differential drive wheel speeds, sends
commands to the ESP32 motor controller via serial, and publishes
encoder tick counts received from the ESP32.
"""

import math
import struct
import threading

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Int32MultiArray

try:
    import serial
    _HAS_SERIAL = True
except ImportError:
    _HAS_SERIAL = False


class _MockSerial:
    """Mock serial port for development without hardware."""

    def __init__(self, port, baudrate, timeout=None):
        self.port = port
        self.baudrate = baudrate
        self.is_open = True
        self._left_ticks = 0
        self._right_ticks = 0

    def write(self, data):
        return len(data)

    def readline(self):
        # Simulate encoder response
        self._left_ticks += 10
        self._right_ticks += 10
        return f'E,{self._left_ticks},{self._right_ticks}\n'.encode()

    def read(self, size=1):
        return b''

    @property
    def in_waiting(self):
        return 0

    def close(self):
        self.is_open = False

    def flush(self):
        pass


class MotorDriverNode(Node):
    """Interfaces with ESP32 motor controller via serial."""

    # Serial protocol:
    # TX to ESP32: "M,<left_speed>,<right_speed>\n"  (speeds in rad/s)
    # RX from ESP32: "E,<left_ticks>,<right_ticks>\n"

    def __init__(self):
        super().__init__('motor_driver')

        # Parameters
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('wheel_radius', 0.075)       # meters
        self.declare_parameter('wheel_separation', 0.40)     # meters
        self.declare_parameter('max_wheel_speed', 10.0)      # rad/s
        self.declare_parameter('serial_timeout', 0.1)        # seconds
        self.declare_parameter('cmd_rate', 20.0)             # Hz

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        timeout = self.get_parameter('serial_timeout').value
        self._wheel_radius = self.get_parameter('wheel_radius').value
        self._wheel_separation = self.get_parameter('wheel_separation').value
        self._max_wheel_speed = self.get_parameter('max_wheel_speed').value

        # Open serial connection
        if _HAS_SERIAL:
            try:
                self._ser = serial.Serial(port, baud, timeout=timeout)
                self.get_logger().info(f'Serial opened: {port} @ {baud}')
            except serial.SerialException as e:
                self.get_logger().error(f'Serial open failed: {e}. Using mock.')
                self._ser = _MockSerial(port, baud, timeout)
        else:
            self.get_logger().warn('pyserial not installed; using mock serial')
            self._ser = _MockSerial(port, baud, timeout)

        # State
        self._target_left = 0.0  # rad/s
        self._target_right = 0.0  # rad/s
        self._lock = threading.Lock()

        # Subscriber
        self._cmd_vel_sub = self.create_subscription(
            Twist, 'cmd_vel', self._cmd_vel_cb, 10
        )

        # Publisher
        self._encoder_pub = self.create_publisher(Int32MultiArray, 'encoder_ticks', 10)

        # Timer for sending commands and reading encoder
        rate = self.get_parameter('cmd_rate').value
        self._serial_timer = self.create_timer(1.0 / rate, self._serial_loop)

        self.get_logger().info('MotorDriver ready')

    def _cmd_vel_cb(self, msg: Twist):
        """Convert Twist to differential drive wheel speeds."""
        linear = msg.linear.x
        angular = msg.angular.z

        # Differential drive inverse kinematics
        left_vel = (linear - angular * self._wheel_separation / 2.0) / self._wheel_radius
        right_vel = (linear + angular * self._wheel_separation / 2.0) / self._wheel_radius

        # Clamp to max speed
        left_vel = max(-self._max_wheel_speed, min(self._max_wheel_speed, left_vel))
        right_vel = max(-self._max_wheel_speed, min(self._max_wheel_speed, right_vel))

        with self._lock:
            self._target_left = left_vel
            self._target_right = right_vel

    def _serial_loop(self):
        """Send motor commands and read encoder ticks."""
        # Send speed command
        with self._lock:
            left = self._target_left
            right = self._target_right

        cmd = f'M,{left:.3f},{right:.3f}\n'
        try:
            self._ser.write(cmd.encode())
        except Exception as e:
            self.get_logger().error(f'Serial write error: {e}')
            return

        # Read encoder response
        try:
            if hasattr(self._ser, 'in_waiting') and self._ser.in_waiting > 0:
                line = self._ser.readline().decode().strip()
                self._parse_encoder(line)
            elif isinstance(self._ser, _MockSerial):
                line = self._ser.readline().decode().strip()
                self._parse_encoder(line)
        except Exception as e:
            self.get_logger().debug(f'Serial read error: {e}')

    def _parse_encoder(self, line: str):
        """Parse encoder tick message from ESP32."""
        # Format: "E,<left_ticks>,<right_ticks>"
        if not line.startswith('E,'):
            return

        parts = line.split(',')
        if len(parts) != 3:
            return

        try:
            left_ticks = int(parts[1])
            right_ticks = int(parts[2])
        except ValueError:
            self.get_logger().debug(f'Invalid encoder data: {line}')
            return

        msg = Int32MultiArray()
        msg.data = [left_ticks, right_ticks]
        self._encoder_pub.publish(msg)

    def destroy_node(self):
        """Stop motors and close serial."""
        # Send stop command
        try:
            self._ser.write(b'M,0.000,0.000\n')
            self._ser.flush()
            self._ser.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
