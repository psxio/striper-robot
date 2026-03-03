"""Simulated GPS node for Gazebo simulation.

Subscribes to the robot's simulated pose (from Gazebo or TF), converts
local XY position to NavSatFix using a configurable datum, and adds
Gaussian noise to simulate RTK-level GPS accuracy.
"""

import math
import random

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix, NavSatStatus
from geometry_msgs.msg import PoseStamped
from geographic_msgs.msg import GeoPoint


class FakeGPSNode(Node):
    """Converts simulated position to GPS coordinates with noise."""

    def __init__(self):
        super().__init__('fake_gps')

        # Parameters
        self.declare_parameter('datum_latitude', 40.4500)
        self.declare_parameter('datum_longitude', -79.9667)
        self.declare_parameter('datum_altitude', 300.0)
        self.declare_parameter('noise_std_m', 0.02)       # RTK-like noise
        self.declare_parameter('publish_rate', 10.0)       # Hz
        self.declare_parameter('frame_id', 'gps_link')
        self.declare_parameter('fix_quality', 4)           # 4 = RTK fixed

        self._datum_lat = self.get_parameter('datum_latitude').value
        self._datum_lon = self.get_parameter('datum_longitude').value
        self._datum_alt = self.get_parameter('datum_altitude').value
        self._noise_std = self.get_parameter('noise_std_m').value
        self._frame_id = self.get_parameter('frame_id').value
        self._fix_quality = self.get_parameter('fix_quality').value

        # Meters-to-degrees conversion at datum latitude
        self._m_per_deg_lat = 111320.0
        self._m_per_deg_lon = 111320.0 * math.cos(math.radians(self._datum_lat))

        # Current simulated position
        self._sim_x = 0.0
        self._sim_y = 0.0
        self._sim_z = 0.0

        # Subscribers
        self._pose_sub = self.create_subscription(
            PoseStamped, 'sim/robot_pose', self._pose_cb, 10
        )
        self._datum_sub = self.create_subscription(
            GeoPoint, 'datum', self._datum_cb, 10
        )

        # Publisher
        self._fix_pub = self.create_publisher(NavSatFix, 'gps/fix', 10)

        # Publish timer
        rate = self.get_parameter('publish_rate').value
        self._timer = self.create_timer(1.0 / rate, self._publish_fix)

        self.get_logger().info(
            f'FakeGPS ready: datum=({self._datum_lat:.6f}, {self._datum_lon:.6f}), '
            f'noise={self._noise_std * 100:.1f}cm'
        )

    def _pose_cb(self, msg: PoseStamped):
        """Update simulated robot position."""
        self._sim_x = msg.pose.position.x
        self._sim_y = msg.pose.position.y
        self._sim_z = msg.pose.position.z

    def _datum_cb(self, msg: GeoPoint):
        """Update datum from datum setter node."""
        self._datum_lat = msg.latitude
        self._datum_lon = msg.longitude
        self._datum_alt = msg.altitude
        self._m_per_deg_lon = 111320.0 * math.cos(math.radians(self._datum_lat))
        self.get_logger().info(
            f'Datum updated: ({self._datum_lat:.6f}, {self._datum_lon:.6f})'
        )

    def _publish_fix(self):
        """Convert local position to GPS and publish with noise."""
        # Add Gaussian noise
        noise_x = random.gauss(0.0, self._noise_std)
        noise_y = random.gauss(0.0, self._noise_std)

        noisy_x = self._sim_x + noise_x
        noisy_y = self._sim_y + noise_y

        # Convert local XY to lat/lon
        latitude = self._datum_lat + (noisy_y / self._m_per_deg_lat)
        longitude = self._datum_lon + (noisy_x / self._m_per_deg_lon)
        altitude = self._datum_alt + self._sim_z

        # Build NavSatFix
        msg = NavSatFix()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id

        # RTK Fixed status
        if self._fix_quality == 4:
            msg.status.status = NavSatStatus.STATUS_GBAS_FIX
        else:
            msg.status.status = NavSatStatus.STATUS_FIX
        msg.status.service = NavSatStatus.SERVICE_GPS

        msg.latitude = latitude
        msg.longitude = longitude
        msg.altitude = altitude

        # Covariance from noise std
        cov = self._noise_std ** 2
        msg.position_covariance[0] = cov
        msg.position_covariance[4] = cov
        msg.position_covariance[8] = cov * 4  # Vertical worse
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_APPROXIMATED

        self._fix_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = FakeGPSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
