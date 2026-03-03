"""Paint controller node for spray synchronization.

Monitors robot position along the current paint segment and commands
the spray valve on/off with configurable lead/lag compensation to
account for physical valve response times.
"""

import math

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point

from striper_msgs.msg import PaintCommand, PaintSegment


class PaintControllerNode(Node):
    """Synchronizes paint spray with robot position along segments."""

    def __init__(self):
        super().__init__('paint_controller')

        # Parameters
        self.declare_parameter('spray_lead_time', 0.050)  # 50ms open early
        self.declare_parameter('spray_lag_time', 0.030)   # 30ms close early
        self.declare_parameter('position_tolerance', 0.05)  # meters
        self.declare_parameter('control_rate', 50.0)  # Hz

        self._spray_lead_time = self.get_parameter('spray_lead_time').value
        self._spray_lag_time = self.get_parameter('spray_lag_time').value
        self._position_tolerance = self.get_parameter('position_tolerance').value

        # State
        self._current_x = 0.0
        self._current_y = 0.0
        self._current_speed = 0.0
        self._active_segment = None
        self._segment_waypoints = []
        self._segment_cumulative_dist = []  # Cumulative distance at each waypoint
        self._segment_total_dist = 0.0
        self._distance_along_segment = 0.0
        self._spray_active = False
        self._prev_x = None
        self._prev_y = None

        # Subscribers
        self._odom_sub = self.create_subscription(
            Odometry, 'odom', self._odom_cb, 10
        )
        self._segment_sub = self.create_subscription(
            PaintSegment, 'current_paint_segment', self._segment_cb, 10
        )

        # Publisher
        self._paint_cmd_pub = self.create_publisher(PaintCommand, 'paint_command', 10)

        # Control loop
        rate = self.get_parameter('control_rate').value
        self._timer = self.create_timer(1.0 / rate, self._control_loop)

        self.get_logger().info(
            f'PaintController ready: lead={self._spray_lead_time * 1000:.0f}ms, '
            f'lag={self._spray_lag_time * 1000:.0f}ms'
        )

    def _odom_cb(self, msg: Odometry):
        """Update current robot position and speed."""
        self._current_x = msg.pose.pose.position.x
        self._current_y = msg.pose.pose.position.y

        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self._current_speed = math.sqrt(vx * vx + vy * vy)

        # Accumulate distance along segment
        if self._prev_x is not None and self._active_segment is not None:
            dx = self._current_x - self._prev_x
            dy = self._current_y - self._prev_y
            self._distance_along_segment += math.sqrt(dx * dx + dy * dy)
        self._prev_x = self._current_x
        self._prev_y = self._current_y

    def _segment_cb(self, msg: PaintSegment):
        """Receive new paint segment to track."""
        self._active_segment = msg
        self._segment_waypoints = list(msg.waypoints)
        self._distance_along_segment = 0.0
        self._prev_x = None
        self._prev_y = None

        # Precompute cumulative distances
        self._segment_cumulative_dist = [0.0]
        total = 0.0
        for i in range(1, len(self._segment_waypoints)):
            dx = self._segment_waypoints[i].x - self._segment_waypoints[i - 1].x
            dy = self._segment_waypoints[i].y - self._segment_waypoints[i - 1].y
            total += math.sqrt(dx * dx + dy * dy)
            self._segment_cumulative_dist.append(total)
        self._segment_total_dist = total

        self.get_logger().info(
            f'New segment: {len(self._segment_waypoints)} waypoints, '
            f'{self._segment_total_dist:.2f}m'
        )

    def _control_loop(self):
        """Determine spray on/off based on position along segment."""
        if self._active_segment is None or self._segment_total_dist <= 0.0:
            return

        # Compute lead/lag distances from current speed
        lead_dist = self._current_speed * self._spray_lead_time
        lag_dist = self._current_speed * self._spray_lag_time

        # Start spraying lead_dist before the segment paint zone begins
        spray_start = max(0.0, -lead_dist)  # Segment starts at distance 0
        # Stop spraying lag_dist before the segment paint zone ends
        spray_end = self._segment_total_dist - lag_dist

        distance = self._distance_along_segment
        should_spray = spray_start <= distance <= spray_end

        if should_spray != self._spray_active:
            cmd = PaintCommand()
            cmd.spray_on = should_spray
            cmd.flow_rate = self._active_segment.speed if should_spray else 0.0
            self._paint_cmd_pub.publish(cmd)
            self._spray_active = should_spray

            action = 'ON' if should_spray else 'OFF'
            self.get_logger().debug(
                f'Spray {action} at distance {distance:.3f}m '
                f'(segment {self._segment_total_dist:.2f}m)'
            )

    def _find_closest_waypoint_distance(self) -> float:
        """Find distance along the segment closest to current position."""
        if not self._segment_waypoints:
            return 0.0

        min_dist_sq = float('inf')
        closest_idx = 0

        for i, wp in enumerate(self._segment_waypoints):
            dx = self._current_x - wp.x
            dy = self._current_y - wp.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_idx = i

        return self._segment_cumulative_dist[closest_idx]

    def destroy_node(self):
        # Ensure spray is off
        cmd = PaintCommand()
        cmd.spray_on = False
        cmd.flow_rate = 0.0
        self._paint_cmd_pub.publish(cmd)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PaintControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
