"""GPS datum setter node.

Manages the GPS datum (origin) for the job site. Provides a SetDatum
service, publishes datum for navsat_transform_node, and supports
auto-setting from the first GPS fix.
"""

import json
import os

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix
from geographic_msgs.msg import GeoPoint

from striper_msgs.srv import SetDatum


class DatumSetterNode(Node):
    """Sets and manages GPS datum for coordinate transforms."""

    def __init__(self):
        super().__init__('datum_setter')

        # Parameters
        self.declare_parameter('auto_set_from_gps', False)
        self.declare_parameter('datum_file', '/tmp/striper_datum.json')
        self.declare_parameter('default_latitude', 0.0)
        self.declare_parameter('default_longitude', 0.0)
        self.declare_parameter('default_altitude', 0.0)

        self._auto_set = self.get_parameter('auto_set_from_gps').value
        self._datum_file = self.get_parameter('datum_file').value

        # Datum state
        self._latitude = self.get_parameter('default_latitude').value
        self._longitude = self.get_parameter('default_longitude').value
        self._altitude = self.get_parameter('default_altitude').value
        self._datum_set = False

        # Try to load saved datum
        self._load_datum()

        # Service
        self._set_datum_srv = self.create_service(
            SetDatum, 'set_datum', self._set_datum_cb
        )

        # Publishers
        self._datum_pub = self.create_publisher(GeoPoint, 'datum', 10, )

        # GPS subscriber for auto-datum
        if self._auto_set:
            self._gps_sub = self.create_subscription(
                NavSatFix, 'gps/fix', self._gps_cb, 10
            )
            self.get_logger().info('Auto-datum from GPS enabled')
        else:
            self._gps_sub = None

        # Publish datum periodically
        self._datum_timer = self.create_timer(1.0, self._publish_datum)

        if self._datum_set:
            self.get_logger().info(
                f'Datum loaded: lat={self._latitude:.8f}, '
                f'lon={self._longitude:.8f}, alt={self._altitude:.2f}'
            )
        else:
            self.get_logger().info('DatumSetter ready (no datum set)')

    def _set_datum_cb(self, request, response):
        """Handle SetDatum service request."""
        self._latitude = request.latitude
        self._longitude = request.longitude
        self._altitude = request.altitude
        self._datum_set = True

        self._save_datum()
        self._publish_datum()

        # Disable auto-set after manual set
        if self._gps_sub is not None:
            self.destroy_subscription(self._gps_sub)
            self._gps_sub = None

        response.success = True
        response.message = (
            f'Datum set: lat={self._latitude:.8f}, '
            f'lon={self._longitude:.8f}, alt={self._altitude:.2f}'
        )
        self.get_logger().info(response.message)
        return response

    def _gps_cb(self, msg: NavSatFix):
        """Auto-set datum from first valid GPS fix."""
        if self._datum_set:
            return

        # Check for valid fix
        if msg.status.status < 0:
            return

        self._latitude = msg.latitude
        self._longitude = msg.longitude
        self._altitude = msg.altitude
        self._datum_set = True

        self._save_datum()
        self._publish_datum()

        self.get_logger().info(
            f'Auto-datum set from GPS: lat={self._latitude:.8f}, '
            f'lon={self._longitude:.8f}, alt={self._altitude:.2f}'
        )

        # Unsubscribe from GPS after auto-set
        if self._gps_sub is not None:
            self.destroy_subscription(self._gps_sub)
            self._gps_sub = None

    def _publish_datum(self):
        """Publish current datum to /datum topic."""
        if not self._datum_set:
            return

        msg = GeoPoint()
        msg.latitude = self._latitude
        msg.longitude = self._longitude
        msg.altitude = self._altitude
        self._datum_pub.publish(msg)

    def _save_datum(self):
        """Persist datum to file."""
        data = {
            'latitude': self._latitude,
            'longitude': self._longitude,
            'altitude': self._altitude,
        }
        try:
            os.makedirs(os.path.dirname(self._datum_file), exist_ok=True)
            with open(self._datum_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.get_logger().debug(f'Datum saved to {self._datum_file}')
        except OSError as e:
            self.get_logger().warn(f'Failed to save datum: {e}')

    def _load_datum(self):
        """Load datum from file if it exists."""
        if not os.path.isfile(self._datum_file):
            return
        try:
            with open(self._datum_file, 'r') as f:
                data = json.load(f)
            self._latitude = data['latitude']
            self._longitude = data['longitude']
            self._altitude = data['altitude']
            self._datum_set = True
        except (OSError, json.JSONDecodeError, KeyError) as e:
            self.get_logger().warn(f'Failed to load datum: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = DatumSetterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
