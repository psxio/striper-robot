"""Geofence boundary enforcement node.

Monitors GPS position against a configurable polygon boundary.
Uses ray casting algorithm for point-in-polygon testing. Publishes
geofence status and violation flags.
"""

import math

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool, String


class GeofenceNode(Node):
    """Enforces GPS polygon boundary for safe operation."""

    def __init__(self):
        super().__init__('geofence')

        # Parameters
        self.declare_parameter('boundary_vertices', [0.0])  # flat list: lat1,lon1,lat2,lon2,...
        self.declare_parameter('buffer_distance', 2.0)       # meters - warning zone
        self.declare_parameter('check_rate', 5.0)             # Hz
        self.declare_parameter('enabled', True)

        self._buffer_dist = self.get_parameter('buffer_distance').value
        self._enabled = self.get_parameter('enabled').value

        # Parse boundary vertices
        self._boundary = []
        vertices_flat = self.get_parameter('boundary_vertices').value
        if len(vertices_flat) >= 6:  # Need at least 3 vertices (6 values)
            for i in range(0, len(vertices_flat) - 1, 2):
                self._boundary.append((vertices_flat[i], vertices_flat[i + 1]))
            self.get_logger().info(
                f'Geofence configured with {len(self._boundary)} vertices'
            )
        else:
            self.get_logger().warn('No valid geofence boundary configured')
            self._enabled = False

        # State
        self._current_lat = 0.0
        self._current_lon = 0.0
        self._has_fix = False
        self._inside_boundary = True
        self._near_boundary = False

        # Subscriber
        self._gps_sub = self.create_subscription(
            NavSatFix, 'gps/fix', self._gps_cb, 10
        )

        # Publishers
        self._violation_pub = self.create_publisher(Bool, 'safety/geofence_violation', 10)
        self._status_pub = self.create_publisher(String, 'geofence/status', 10)

        # Check timer
        rate = self.get_parameter('check_rate').value
        self._timer = self.create_timer(1.0 / rate, self._check_geofence)

        self.get_logger().info(f'Geofence node ready (enabled={self._enabled})')

    def _gps_cb(self, msg: NavSatFix):
        """Update current GPS position."""
        if msg.status.status < 0:
            return
        self._current_lat = msg.latitude
        self._current_lon = msg.longitude
        self._has_fix = True

    def _check_geofence(self):
        """Check if robot is within geofence boundary."""
        if not self._enabled or not self._has_fix:
            # Publish safe when disabled or no fix
            violation_msg = Bool()
            violation_msg.data = False
            self._violation_pub.publish(violation_msg)
            return

        # Point-in-polygon test
        inside = self._point_in_polygon(
            self._current_lat, self._current_lon, self._boundary
        )

        # Check if near boundary (within buffer distance)
        min_dist = self._distance_to_boundary(
            self._current_lat, self._current_lon, self._boundary
        )
        near_boundary = min_dist < self._buffer_dist

        self._inside_boundary = inside
        self._near_boundary = near_boundary

        # Publish violation flag
        violation_msg = Bool()
        violation_msg.data = not inside
        self._violation_pub.publish(violation_msg)

        # Publish status
        status_msg = String()
        if not inside:
            status_msg.data = f'VIOLATION: Outside geofence ({min_dist:.1f}m from boundary)'
            self.get_logger().error(status_msg.data, throttle_duration_sec=2.0)
        elif near_boundary:
            status_msg.data = f'WARNING: Near boundary ({min_dist:.1f}m)'
            self.get_logger().warn(status_msg.data, throttle_duration_sec=5.0)
        else:
            status_msg.data = f'OK: Inside geofence ({min_dist:.1f}m from boundary)'
        self._status_pub.publish(status_msg)

    @staticmethod
    def _point_in_polygon(lat, lon, polygon):
        """Ray casting algorithm for point-in-polygon test."""
        n = len(polygon)
        if n < 3:
            return True  # No valid polygon = no restriction

        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = polygon[i]
            yj, xj = polygon[j]

            if ((yi > lon) != (yj > lon)) and \
               (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
                inside = not inside
            j = i

        return inside

    @staticmethod
    def _distance_to_boundary(lat, lon, polygon):
        """Approximate minimum distance from point to polygon boundary in meters."""
        if len(polygon) < 2:
            return float('inf')

        min_dist = float('inf')
        n = len(polygon)

        for i in range(n):
            j = (i + 1) % n
            lat1, lon1 = polygon[i]
            lat2, lon2 = polygon[j]

            dist = GeofenceNode._point_to_segment_distance(
                lat, lon, lat1, lon1, lat2, lon2
            )
            if dist < min_dist:
                min_dist = dist

        return min_dist

    @staticmethod
    def _point_to_segment_distance(plat, plon, lat1, lon1, lat2, lon2):
        """Distance from point to line segment in meters (Haversine approx)."""
        # Convert to approximate local meters
        # 1 degree lat ~ 111320m, 1 degree lon ~ 111320 * cos(lat)
        cos_lat = math.cos(math.radians(plat))
        m_per_deg_lat = 111320.0
        m_per_deg_lon = 111320.0 * cos_lat

        px = (plon - lon1) * m_per_deg_lon
        py = (plat - lat1) * m_per_deg_lat
        sx = (lon2 - lon1) * m_per_deg_lon
        sy = (lat2 - lat1) * m_per_deg_lat

        seg_len_sq = sx * sx + sy * sy
        if seg_len_sq < 1e-10:
            return math.sqrt(px * px + py * py)

        t = max(0.0, min(1.0, (px * sx + py * sy) / seg_len_sq))
        proj_x = t * sx
        proj_y = t * sy

        dx = px - proj_x
        dy = py - proj_y
        return math.sqrt(dx * dx + dy * dy)


def main(args=None):
    rclpy.init(args=args)
    node = GeofenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
