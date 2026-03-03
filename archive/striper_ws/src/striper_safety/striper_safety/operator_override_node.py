"""Operator manual override node.

Processes gamepad/joystick input for manual robot control. Implements
deadman switch, joystick-to-cmd_vel mapping, and mode switching
between AUTO, MANUAL, and ESTOP.
"""

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import String


class OperatorOverrideNode(Node):
    """Gamepad-based manual control with deadman switch."""

    MODE_AUTO = 'AUTO'
    MODE_MANUAL = 'MANUAL'
    MODE_ESTOP = 'ESTOP'

    def __init__(self):
        super().__init__('operator_override')

        # Parameters
        self.declare_parameter('deadman_button', 4)       # L1 / LB
        self.declare_parameter('estop_button', 7)         # Start / Menu
        self.declare_parameter('mode_toggle_button', 6)   # R1 / RB
        self.declare_parameter('linear_axis', 1)          # Left stick Y
        self.declare_parameter('angular_axis', 0)         # Left stick X
        self.declare_parameter('max_linear_speed', 1.0)   # m/s
        self.declare_parameter('max_angular_speed', 1.5)  # rad/s
        self.declare_parameter('linear_scale', 0.5)       # Scale factor
        self.declare_parameter('angular_scale', 1.0)      # Scale factor
        self.declare_parameter('publish_rate', 20.0)      # Hz

        self._deadman_btn = self.get_parameter('deadman_button').value
        self._estop_btn = self.get_parameter('estop_button').value
        self._mode_btn = self.get_parameter('mode_toggle_button').value
        self._linear_axis = self.get_parameter('linear_axis').value
        self._angular_axis = self.get_parameter('angular_axis').value
        self._max_linear = self.get_parameter('max_linear_speed').value
        self._max_angular = self.get_parameter('max_angular_speed').value
        self._linear_scale = self.get_parameter('linear_scale').value
        self._angular_scale = self.get_parameter('angular_scale').value

        # State
        self._mode = self.MODE_AUTO
        self._deadman_held = False
        self._manual_cmd = Twist()
        self._prev_mode_btn = False
        self._prev_estop_btn = False

        # Subscriber
        self._joy_sub = self.create_subscription(Joy, 'joy', self._joy_cb, 10)

        # Publishers
        self._cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel_manual', 10)
        self._mode_pub = self.create_publisher(String, 'operator/mode', 10)
        self._override_active_pub = self.create_publisher(
            String, 'operator/override_active', 10
        )

        # Publish timer
        rate = self.get_parameter('publish_rate').value
        self._timer = self.create_timer(1.0 / rate, self._publish)

        self.get_logger().info('OperatorOverride ready (mode: AUTO)')

    def _joy_cb(self, msg: Joy):
        """Process gamepad input."""
        if len(msg.buttons) == 0:
            return

        # Deadman switch
        self._deadman_held = (
            self._deadman_btn < len(msg.buttons) and
            msg.buttons[self._deadman_btn] == 1
        )

        # E-stop button (toggle)
        estop_pressed = (
            self._estop_btn < len(msg.buttons) and
            msg.buttons[self._estop_btn] == 1
        )
        if estop_pressed and not self._prev_estop_btn:
            if self._mode == self.MODE_ESTOP:
                self._mode = self.MODE_AUTO
                self.get_logger().info('E-stop released -> AUTO mode')
            else:
                self._mode = self.MODE_ESTOP
                self.get_logger().warn('E-STOP activated via gamepad')
        self._prev_estop_btn = estop_pressed

        # Mode toggle (AUTO <-> MANUAL)
        mode_pressed = (
            self._mode_btn < len(msg.buttons) and
            msg.buttons[self._mode_btn] == 1
        )
        if mode_pressed and not self._prev_mode_btn and self._mode != self.MODE_ESTOP:
            if self._mode == self.MODE_AUTO:
                self._mode = self.MODE_MANUAL
                self.get_logger().info('Switched to MANUAL mode')
            else:
                self._mode = self.MODE_AUTO
                self.get_logger().info('Switched to AUTO mode')
        self._prev_mode_btn = mode_pressed

        # Map joystick to cmd_vel (only if deadman held and in manual mode)
        if self._deadman_held and self._mode == self.MODE_MANUAL:
            linear_input = 0.0
            angular_input = 0.0

            if self._linear_axis < len(msg.axes):
                linear_input = msg.axes[self._linear_axis]
            if self._angular_axis < len(msg.axes):
                angular_input = msg.axes[self._angular_axis]

            self._manual_cmd.linear.x = (
                linear_input * self._linear_scale * self._max_linear
            )
            self._manual_cmd.angular.z = (
                angular_input * self._angular_scale * self._max_angular
            )
        else:
            self._manual_cmd = Twist()

    def _publish(self):
        """Publish mode and manual commands."""
        # Publish mode
        mode_msg = String()
        mode_msg.data = self._mode
        self._mode_pub.publish(mode_msg)

        # In manual mode with deadman held, publish cmd_vel
        if self._mode == self.MODE_MANUAL and self._deadman_held:
            self._cmd_vel_pub.publish(self._manual_cmd)
            override_msg = String()
            override_msg.data = 'ACTIVE'
            self._override_active_pub.publish(override_msg)
        elif self._mode == self.MODE_ESTOP:
            # Publish zero velocity
            self._cmd_vel_pub.publish(Twist())
        else:
            override_msg = String()
            override_msg.data = 'INACTIVE'
            self._override_active_pub.publish(override_msg)


def main(args=None):
    rclpy.init(args=args)
    node = OperatorOverrideNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
