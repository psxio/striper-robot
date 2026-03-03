"""Wheel odometry publisher node.

Computes differential drive kinematics from encoder tick counts
and publishes nav_msgs/Odometry plus the odom -> base_link TF.
"""

import math

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from std_msgs.msg import Int32MultiArray
from tf2_ros import TransformBroadcaster


class OdomPublisherNode(Node):
    """Computes and publishes wheel odometry from encoder ticks."""

    def __init__(self):
        super().__init__('odom_publisher')

        # Parameters
        self.declare_parameter('wheel_radius', 0.075)       # meters
        self.declare_parameter('wheel_separation', 0.40)     # meters
        self.declare_parameter('ticks_per_rev', 1440)        # encoder resolution
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('publish_tf', True)

        self._wheel_radius = self.get_parameter('wheel_radius').value
        self._wheel_separation = self.get_parameter('wheel_separation').value
        self._ticks_per_rev = self.get_parameter('ticks_per_rev').value
        self._odom_frame = self.get_parameter('odom_frame').value
        self._base_frame = self.get_parameter('base_frame').value
        self._publish_tf = self.get_parameter('publish_tf').value

        # Distance per tick
        self._dist_per_tick = (2.0 * math.pi * self._wheel_radius) / self._ticks_per_rev

        # Odometry state
        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        self._vx = 0.0
        self._vtheta = 0.0

        # Previous encoder values
        self._prev_left_ticks = None
        self._prev_right_ticks = None
        self._prev_time = None

        # TF broadcaster
        self._tf_broadcaster = TransformBroadcaster(self)

        # Subscriber for encoder ticks [left, right]
        self._encoder_sub = self.create_subscription(
            Int32MultiArray, 'encoder_ticks', self._encoder_cb, 10
        )

        # Publisher
        self._odom_pub = self.create_publisher(Odometry, 'wheel_odom', 10)

        self.get_logger().info(
            f'OdomPublisher ready: wheel_r={self._wheel_radius}m, '
            f'separation={self._wheel_separation}m, '
            f'ticks/rev={self._ticks_per_rev}'
        )

    def _encoder_cb(self, msg: Int32MultiArray):
        """Process encoder tick counts and compute odometry."""
        if len(msg.data) < 2:
            self.get_logger().warn('Encoder message needs [left, right] ticks')
            return

        left_ticks = msg.data[0]
        right_ticks = msg.data[1]
        current_time = self.get_clock().now()

        if self._prev_left_ticks is None:
            # First message - just store values
            self._prev_left_ticks = left_ticks
            self._prev_right_ticks = right_ticks
            self._prev_time = current_time
            return

        # Compute tick deltas
        delta_left = left_ticks - self._prev_left_ticks
        delta_right = right_ticks - self._prev_right_ticks

        # Time delta
        dt = (current_time - self._prev_time).nanoseconds * 1e-9
        if dt <= 0.0:
            return

        # Convert ticks to distances
        dist_left = delta_left * self._dist_per_tick
        dist_right = delta_right * self._dist_per_tick

        # Differential drive kinematics
        dist_center = (dist_left + dist_right) / 2.0
        delta_theta = (dist_right - dist_left) / self._wheel_separation

        # Update pose
        if abs(delta_theta) < 1e-6:
            # Straight line
            self._x += dist_center * math.cos(self._theta)
            self._y += dist_center * math.sin(self._theta)
        else:
            # Arc motion
            radius = dist_center / delta_theta
            self._x += radius * (math.sin(self._theta + delta_theta) - math.sin(self._theta))
            self._y -= radius * (math.cos(self._theta + delta_theta) - math.cos(self._theta))

        self._theta += delta_theta
        # Normalize theta to [-pi, pi]
        self._theta = math.atan2(math.sin(self._theta), math.cos(self._theta))

        # Compute velocities
        self._vx = dist_center / dt
        self._vtheta = delta_theta / dt

        # Publish odometry
        self._publish_odom(current_time)

        # Publish TF
        if self._publish_tf:
            self._publish_transform(current_time)

        # Store previous values
        self._prev_left_ticks = left_ticks
        self._prev_right_ticks = right_ticks
        self._prev_time = current_time

    def _publish_odom(self, stamp):
        """Publish Odometry message."""
        odom = Odometry()
        odom.header.stamp = stamp.to_msg()
        odom.header.frame_id = self._odom_frame
        odom.child_frame_id = self._base_frame

        # Position
        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.position.z = 0.0

        # Orientation (quaternion from yaw)
        odom.pose.pose.orientation.z = math.sin(self._theta / 2.0)
        odom.pose.pose.orientation.w = math.cos(self._theta / 2.0)

        # Pose covariance (x, y, theta diagonal)
        odom.pose.covariance[0] = 0.01   # x
        odom.pose.covariance[7] = 0.01   # y
        odom.pose.covariance[35] = 0.03  # yaw

        # Velocity
        odom.twist.twist.linear.x = self._vx
        odom.twist.twist.angular.z = self._vtheta

        # Twist covariance
        odom.twist.covariance[0] = 0.01   # vx
        odom.twist.covariance[35] = 0.03  # vyaw

        self._odom_pub.publish(odom)

    def _publish_transform(self, stamp):
        """Broadcast odom -> base_link transform."""
        t = TransformStamped()
        t.header.stamp = stamp.to_msg()
        t.header.frame_id = self._odom_frame
        t.child_frame_id = self._base_frame

        t.transform.translation.x = self._x
        t.transform.translation.y = self._y
        t.transform.translation.z = 0.0

        t.transform.rotation.z = math.sin(self._theta / 2.0)
        t.transform.rotation.w = math.cos(self._theta / 2.0)

        self._tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = OdomPublisherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
