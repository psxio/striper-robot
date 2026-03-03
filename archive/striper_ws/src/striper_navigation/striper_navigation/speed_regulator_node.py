"""Speed regulator node for constant paint speed control.

Monitors robot speed via odometry and publishes velocity overrides
to maintain a constant painting speed with smooth ramp-up/down.
"""

import math

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64


class SpeedRegulatorNode(Node):
    """PID-like speed controller for consistent paint application."""

    def __init__(self):
        super().__init__('speed_regulator')

        # Parameters
        self.declare_parameter('target_speed', 0.5)  # m/s default paint speed
        self.declare_parameter('kp', 1.0)
        self.declare_parameter('ki', 0.1)
        self.declare_parameter('kd', 0.05)
        self.declare_parameter('max_accel', 0.5)  # m/s^2 max acceleration
        self.declare_parameter('ramp_distance', 0.3)  # meters to ramp up/down
        self.declare_parameter('control_rate', 20.0)  # Hz
        self.declare_parameter('max_speed', 1.0)  # m/s hard limit (matches nav2 max_velocity)
        self.declare_parameter('min_speed', 0.05)  # m/s minimum to consider moving

        self._target_speed = self.get_parameter('target_speed').value
        self._kp = self.get_parameter('kp').value
        self._ki = self.get_parameter('ki').value
        self._kd = self.get_parameter('kd').value
        self._max_accel = self.get_parameter('max_accel').value
        self._ramp_distance = self.get_parameter('ramp_distance').value
        self._max_speed = self.get_parameter('max_speed').value
        self._min_speed = self.get_parameter('min_speed').value

        # PID state
        self._current_speed = 0.0
        self._integral_error = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._enabled = False

        # Ramp state
        self._ramp_phase = 'idle'  # idle, ramp_up, steady, ramp_down
        self._distance_in_segment = 0.0
        self._segment_length = 0.0
        self._prev_x = None
        self._prev_y = None

        # Subscribers
        self._odom_sub = self.create_subscription(
            Odometry, 'odom', self._odom_cb, 10
        )
        self._setpoint_sub = self.create_subscription(
            Float64, 'paint_speed_setpoint', self._setpoint_cb, 10
        )

        # Publisher for speed override
        self._cmd_vel_pub = self.create_publisher(Twist, 'speed_override_cmd_vel', 10)

        # Control loop timer
        rate = self.get_parameter('control_rate').value
        self._control_timer = self.create_timer(1.0 / rate, self._control_loop)

        self.get_logger().info(
            f'SpeedRegulator ready: target={self._target_speed} m/s, '
            f'PID=({self._kp}, {self._ki}, {self._kd})'
        )

    def _odom_cb(self, msg: Odometry):
        """Update current speed from odometry."""
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self._current_speed = math.sqrt(vx * vx + vy * vy)

        # Track distance along segment
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        if self._prev_x is not None and self._enabled:
            dx = x - self._prev_x
            dy = y - self._prev_y
            self._distance_in_segment += math.sqrt(dx * dx + dy * dy)
        self._prev_x = x
        self._prev_y = y

    def _setpoint_cb(self, msg: Float64):
        """Update target paint speed."""
        self._target_speed = min(msg.data, self._max_speed)
        if self._target_speed > 0.0:
            self._enabled = True
            self._ramp_phase = 'ramp_up'
            self._distance_in_segment = 0.0
            self._integral_error = 0.0
            self._prev_error = 0.0
            self.get_logger().info(f'Speed setpoint: {self._target_speed:.2f} m/s')
        else:
            self._enabled = False
            self._ramp_phase = 'idle'

    def _compute_ramp_factor(self) -> float:
        """Compute speed scaling factor for ramp up/down."""
        if self._ramp_distance <= 0.0:
            return 1.0

        if self._ramp_phase == 'ramp_up':
            factor = min(1.0, self._distance_in_segment / self._ramp_distance)
            if factor >= 1.0:
                self._ramp_phase = 'steady'
            return max(0.1, factor)

        elif self._ramp_phase == 'ramp_down':
            remaining = max(0.0, self._segment_length - self._distance_in_segment)
            factor = min(1.0, remaining / self._ramp_distance)
            return max(0.1, factor)

        return 1.0

    def _control_loop(self):
        """PID control loop to maintain target speed."""
        if not self._enabled:
            return

        ramp_factor = self._compute_ramp_factor()
        effective_target = self._target_speed * ramp_factor

        # PID error
        error = effective_target - self._current_speed
        self._integral_error += error
        derivative = error - self._prev_error

        # Anti-windup: clamp integral
        max_integral = self._max_speed / max(self._ki, 0.001)
        self._integral_error = max(-max_integral, min(max_integral, self._integral_error))

        # PID output
        output = (
            self._kp * error
            + self._ki * self._integral_error
            + self._kd * derivative
        )

        # Rate limit acceleration
        rate = self.get_parameter('control_rate').value
        max_delta = self._max_accel / rate
        output = max(
            self._prev_output - max_delta,
            min(self._prev_output + max_delta, output),
        )

        # Clamp to valid range
        output = max(0.0, min(self._max_speed, output))

        self._prev_error = error
        self._prev_output = output

        # Publish speed override
        cmd = Twist()
        cmd.linear.x = output
        self._cmd_vel_pub.publish(cmd)

    def start_ramp_down(self, segment_length: float):
        """Signal that segment is ending; begin ramp down."""
        self._segment_length = segment_length
        self._ramp_phase = 'ramp_down'

    def destroy_node(self):
        # Publish zero speed on shutdown
        cmd = Twist()
        self._cmd_vel_pub.publish(cmd)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SpeedRegulatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
