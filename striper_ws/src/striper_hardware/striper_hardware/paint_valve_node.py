"""Paint solenoid valve control node.

Controls a GPIO-driven solenoid valve for paint spraying. Includes
safety auto-close after maximum spray duration and valve state reporting.
"""

import time

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool

from striper_msgs.msg import PaintCommand

# Try to import RPi.GPIO; fall back to mock for non-Pi systems
try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except (ImportError, RuntimeError):
    _HAS_GPIO = False


class _MockGPIO:
    """Mock GPIO for development on non-Raspberry Pi systems."""
    BCM = 'BCM'
    OUT = 'OUT'
    IN = 'IN'
    HIGH = 1
    LOW = 0

    def setmode(self, mode):
        pass

    def setup(self, pin, direction, initial=None):
        pass

    def output(self, pin, value):
        pass

    def cleanup(self, pin=None):
        pass


class PaintValveNode(Node):
    """Controls the paint solenoid valve via GPIO."""

    def __init__(self):
        super().__init__('paint_valve')

        # Parameters
        self.declare_parameter('gpio_pin', 17)
        self.declare_parameter('open_delay_ms', 10.0)
        self.declare_parameter('close_delay_ms', 5.0)
        self.declare_parameter('max_spray_duration', 30.0)  # seconds; safety limit
        self.declare_parameter('active_high', True)

        self._gpio_pin = self.get_parameter('gpio_pin').value
        self._open_delay = self.get_parameter('open_delay_ms').value / 1000.0
        self._close_delay = self.get_parameter('close_delay_ms').value / 1000.0
        self._max_spray = self.get_parameter('max_spray_duration').value
        self._active_high = self.get_parameter('active_high').value

        # GPIO setup
        if _HAS_GPIO:
            self._gpio = GPIO
            self.get_logger().info('Using RPi.GPIO for valve control')
        else:
            self._gpio = _MockGPIO()
            self.get_logger().warn('RPi.GPIO not available; using mock GPIO')

        self._gpio.setmode(self._gpio.BCM)
        initial = self._gpio.LOW if self._active_high else self._gpio.HIGH
        self._gpio.setup(self._gpio_pin, self._gpio.OUT, initial=initial)

        # State
        self._valve_open = False
        self._spray_start_time = None

        # Subscriber
        self._cmd_sub = self.create_subscription(
            PaintCommand, 'paint_command', self._paint_cmd_cb, 10
        )

        # Publishers
        self._state_pub = self.create_publisher(Bool, 'paint_valve_state', 10)

        # Safety timer: check for stuck-open valve
        self._safety_timer = self.create_timer(0.5, self._safety_check)

        # State publish timer
        self._state_timer = self.create_timer(0.2, self._publish_state)

        self.get_logger().info(
            f'PaintValve ready: GPIO pin {self._gpio_pin}, '
            f'max spray {self._max_spray}s'
        )

    def _paint_cmd_cb(self, msg: PaintCommand):
        """Handle paint command: open or close valve."""
        if msg.spray_on and not self._valve_open:
            self._open_valve()
        elif not msg.spray_on and self._valve_open:
            self._close_valve()

    def _open_valve(self):
        """Open the solenoid valve."""
        level = self._gpio.HIGH if self._active_high else self._gpio.LOW
        self._gpio.output(self._gpio_pin, level)
        self._valve_open = True
        self._spray_start_time = time.monotonic()
        self.get_logger().info('Valve OPEN')

    def _close_valve(self):
        """Close the solenoid valve."""
        level = self._gpio.LOW if self._active_high else self._gpio.HIGH
        self._gpio.output(self._gpio_pin, level)
        self._valve_open = False
        self._spray_start_time = None
        self.get_logger().info('Valve CLOSED')

    def _safety_check(self):
        """Auto-close valve if spray duration exceeds maximum."""
        if not self._valve_open or self._spray_start_time is None:
            return

        elapsed = time.monotonic() - self._spray_start_time
        if elapsed > self._max_spray:
            self.get_logger().error(
                f'SAFETY: Valve open for {elapsed:.1f}s > max {self._max_spray}s. '
                f'Auto-closing!'
            )
            self._close_valve()

    def _publish_state(self):
        """Publish current valve state."""
        msg = Bool()
        msg.data = self._valve_open
        self._state_pub.publish(msg)

    def destroy_node(self):
        """Ensure valve is closed and GPIO cleaned up."""
        if self._valve_open:
            self._close_valve()
        self._gpio.cleanup(self._gpio_pin)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PaintValveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
