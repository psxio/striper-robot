"""Paint trail visualizer node for RViz.

Subscribes to PaintCommand and robot position. When spray is on,
records the robot's position trail and publishes it as a MarkerArray
of line strips in RViz, colored to match the paint color.
"""

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA

from striper_msgs.msg import PaintCommand, PaintSegment


class PaintVisualizerNode(Node):
    """Visualizes paint trail in RViz as line strip markers."""

    # Color name to RGBA mapping
    COLORS = {
        'white': (1.0, 1.0, 1.0, 1.0),
        'yellow': (1.0, 0.9, 0.0, 1.0),
        'blue': (0.0, 0.3, 0.8, 1.0),
        'red': (0.9, 0.1, 0.1, 1.0),
        'green': (0.0, 0.7, 0.1, 1.0),
        'orange': (1.0, 0.5, 0.0, 1.0),
    }

    def __init__(self):
        super().__init__('paint_visualizer')

        # Parameters
        self.declare_parameter('default_color', 'white')
        self.declare_parameter('default_line_width', 0.10)  # meters
        self.declare_parameter('min_point_spacing', 0.02)    # meters between trail points
        self.declare_parameter('publish_rate', 2.0)          # Hz
        self.declare_parameter('frame_id', 'map')

        self._default_color = self.get_parameter('default_color').value
        self._default_width = self.get_parameter('default_line_width').value
        self._min_spacing = self.get_parameter('min_point_spacing').value
        self._frame_id = self.get_parameter('frame_id').value

        # State
        self._spray_on = False
        self._current_color = self._default_color
        self._current_width = self._default_width
        self._current_x = 0.0
        self._current_y = 0.0

        # Trail storage: list of completed line strips
        self._completed_trails = []  # List of (points, color, width)
        self._active_trail = []      # Current trail being recorded
        self._marker_id = 0

        # Last recorded point (for spacing)
        self._last_trail_x = None
        self._last_trail_y = None

        # Subscribers
        self._paint_sub = self.create_subscription(
            PaintCommand, 'paint_command', self._paint_cb, 10
        )
        self._odom_sub = self.create_subscription(
            Odometry, 'odom', self._odom_cb, 10
        )
        self._segment_sub = self.create_subscription(
            PaintSegment, 'current_paint_segment', self._segment_cb, 10
        )

        # Publisher
        self._marker_pub = self.create_publisher(MarkerArray, 'paint_trail', 10)

        # Publish timer
        rate = self.get_parameter('publish_rate').value
        self._timer = self.create_timer(1.0 / rate, self._publish_markers)

        self.get_logger().info('PaintVisualizer ready')

    def _paint_cb(self, msg: PaintCommand):
        """Handle spray on/off transitions."""
        if msg.spray_on and not self._spray_on:
            # Spray turning on: start new trail
            self._active_trail = []
            self._last_trail_x = None
            self._last_trail_y = None
            self._spray_on = True
            self.get_logger().debug('Paint visualizer: spray ON')

        elif not msg.spray_on and self._spray_on:
            # Spray turning off: save completed trail
            if len(self._active_trail) >= 2:
                self._completed_trails.append((
                    list(self._active_trail),
                    self._current_color,
                    self._current_width,
                ))
            self._active_trail = []
            self._spray_on = False
            self.get_logger().debug('Paint visualizer: spray OFF')

    def _odom_cb(self, msg: Odometry):
        """Record position when spraying."""
        self._current_x = msg.pose.pose.position.x
        self._current_y = msg.pose.pose.position.y

        if not self._spray_on:
            return

        # Check minimum spacing
        if self._last_trail_x is not None:
            dx = self._current_x - self._last_trail_x
            dy = self._current_y - self._last_trail_y
            dist_sq = dx * dx + dy * dy
            if dist_sq < self._min_spacing * self._min_spacing:
                return

        self._active_trail.append((self._current_x, self._current_y))
        self._last_trail_x = self._current_x
        self._last_trail_y = self._current_y

    def _segment_cb(self, msg: PaintSegment):
        """Update color and width from current segment."""
        if msg.color:
            self._current_color = msg.color.lower()
        if msg.line_width > 0.0:
            self._current_width = msg.line_width

    def _color_to_rgba(self, color_name: str) -> ColorRGBA:
        """Convert color name to RGBA."""
        r, g, b, a = self.COLORS.get(color_name, self.COLORS['white'])
        rgba = ColorRGBA()
        rgba.r = r
        rgba.g = g
        rgba.b = b
        rgba.a = a
        return rgba

    def _publish_markers(self):
        """Publish all paint trails as MarkerArray."""
        marker_array = MarkerArray()
        stamp = self.get_clock().now().to_msg()

        # Completed trails
        for idx, (points, color, width) in enumerate(self._completed_trails):
            marker = Marker()
            marker.header.stamp = stamp
            marker.header.frame_id = self._frame_id
            marker.ns = 'paint_trail'
            marker.id = idx
            marker.type = Marker.LINE_STRIP
            marker.action = Marker.ADD
            marker.scale.x = width  # Line width

            marker.color = self._color_to_rgba(color)

            for px, py in points:
                p = Point()
                p.x = px
                p.y = py
                p.z = 0.005  # Slightly above ground
                marker.points.append(p)

            marker.pose.orientation.w = 1.0
            marker_array.markers.append(marker)

        # Active trail (currently spraying)
        if self._spray_on and len(self._active_trail) >= 2:
            marker = Marker()
            marker.header.stamp = stamp
            marker.header.frame_id = self._frame_id
            marker.ns = 'paint_trail'
            marker.id = len(self._completed_trails)
            marker.type = Marker.LINE_STRIP
            marker.action = Marker.ADD
            marker.scale.x = self._current_width

            marker.color = self._color_to_rgba(self._current_color)

            for px, py in self._active_trail:
                p = Point()
                p.x = px
                p.y = py
                p.z = 0.005
                marker.points.append(p)

            marker.pose.orientation.w = 1.0
            marker_array.markers.append(marker)

        if marker_array.markers:
            self._marker_pub.publish(marker_array)


def main(args=None):
    rclpy.init(args=args)
    node = PaintVisualizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
