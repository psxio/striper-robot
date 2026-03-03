"""ZED-F9P GPS driver node.

Serial communication with u-blox ZED-F9P GNSS receiver. Parses NMEA
GGA sentences, publishes NavSatFix, and supports RTCM correction
input for RTK operation.
"""

import threading

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Float32, String, UInt8MultiArray

try:
    import serial
    _HAS_SERIAL = True
except ImportError:
    _HAS_SERIAL = False


class _MockSerial:
    """Mock serial for development without GPS hardware."""

    def __init__(self, port, baudrate, timeout=None):
        self.is_open = True
        self._count = 0

    def readline(self):
        self._count += 1
        # Simulate a GGA sentence (Pittsburgh, PA area)
        return (
            b'$GPGGA,120000.00,4027.0000,N,07958.0000,W,'
            b'4,12,0.8,300.0,M,-33.0,M,,*6A\r\n'
        )

    def write(self, data):
        return len(data)

    @property
    def in_waiting(self):
        return 50

    def close(self):
        self.is_open = False


class GPSNode(Node):
    """Publishes GPS fixes from a u-blox ZED-F9P receiver."""

    # NMEA GGA fix quality to NavSatStatus mapping
    FIX_QUALITY = {
        0: (NavSatStatus.STATUS_NO_FIX, 'No fix'),
        1: (NavSatStatus.STATUS_FIX, 'GPS fix'),
        2: (NavSatStatus.STATUS_SBAS_FIX, 'DGPS'),
        4: (NavSatStatus.STATUS_GBAS_FIX, 'RTK fixed'),
        5: (NavSatStatus.STATUS_GBAS_FIX, 'RTK float'),
    }

    def __init__(self):
        super().__init__('gps_node')

        # Parameters
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('rtcm_port', '')  # Optional RTCM serial port
        self.declare_parameter('rtcm_baud', 115200)
        self.declare_parameter('frame_id', 'gps_link')
        self.declare_parameter('publish_rate', 10.0)  # Hz (rate limit)

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        self._frame_id = self.get_parameter('frame_id').value
        rtcm_port = self.get_parameter('rtcm_port').value
        rtcm_baud = self.get_parameter('rtcm_baud').value

        # Open GPS serial
        if _HAS_SERIAL:
            try:
                self._ser = serial.Serial(port, baud, timeout=1.0)
                self.get_logger().info(f'GPS serial opened: {port} @ {baud}')
            except serial.SerialException as e:
                self.get_logger().error(f'GPS serial failed: {e}. Using mock.')
                self._ser = _MockSerial(port, baud)
        else:
            self.get_logger().warn('pyserial not installed; using mock GPS')
            self._ser = _MockSerial(port, baud)

        # Open RTCM serial port if configured
        self._rtcm_ser = None
        if rtcm_port and _HAS_SERIAL:
            try:
                self._rtcm_ser = serial.Serial(rtcm_port, rtcm_baud, timeout=0.1)
                self.get_logger().info(f'RTCM port opened: {rtcm_port}')
            except serial.SerialException as e:
                self.get_logger().warn(f'RTCM port failed: {e}')

        # State
        self._latest_fix = None
        self._lock = threading.Lock()

        # Publishers
        self._fix_pub = self.create_publisher(NavSatFix, 'gps/fix', 10)
        self._hdop_pub = self.create_publisher(Float32, 'gps/hdop', 10)
        self._quality_pub = self.create_publisher(String, 'gps/fix_quality', 10)

        # RTCM correction subscribers (for network-based corrections)
        # UInt8MultiArray from ntrip_client_node (preferred binary format)
        self._rtcm_bin_sub = self.create_subscription(
            UInt8MultiArray, 'rtcm_corrections', self._rtcm_bin_cb, 10
        )
        # Legacy String subscriber on a separate topic for backward compat
        self._rtcm_sub = self.create_subscription(
            String, 'rtcm_corrections_legacy', self._rtcm_cb, 10
        )

        # Serial read thread
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

        # Publish timer
        rate = self.get_parameter('publish_rate').value
        self._timer = self.create_timer(1.0 / rate, self._publish)

        self.get_logger().info('GPS node ready')

    def _read_loop(self):
        """Background thread to read NMEA sentences from GPS."""
        while self._running:
            try:
                line = self._ser.readline().decode('ascii', errors='ignore').strip()
                if line.startswith('$G') and 'GGA' in line:
                    fix = self._parse_gga(line)
                    if fix is not None:
                        with self._lock:
                            self._latest_fix = fix
            except Exception as e:
                self.get_logger().debug(f'GPS read error: {e}')

    def _parse_gga(self, sentence: str):
        """Parse NMEA GGA sentence into NavSatFix data."""
        # Remove checksum
        if '*' in sentence:
            sentence = sentence[:sentence.index('*')]

        parts = sentence.split(',')
        if len(parts) < 15:
            return None

        try:
            # Fix quality
            fix_quality = int(parts[6]) if parts[6] else 0

            if fix_quality == 0:
                return {
                    'fix_quality': 0,
                    'latitude': 0.0,
                    'longitude': 0.0,
                    'altitude': 0.0,
                    'hdop': 99.9,
                    'num_sats': 0,
                }

            # Latitude: DDMM.MMMM -> decimal degrees
            lat_raw = float(parts[2])
            lat_deg = int(lat_raw / 100)
            lat_min = lat_raw - lat_deg * 100
            latitude = lat_deg + lat_min / 60.0
            if parts[3] == 'S':
                latitude = -latitude

            # Longitude: DDDMM.MMMM -> decimal degrees
            lon_raw = float(parts[4])
            lon_deg = int(lon_raw / 100)
            lon_min = lon_raw - lon_deg * 100
            longitude = lon_deg + lon_min / 60.0
            if parts[5] == 'W':
                longitude = -longitude

            # Altitude
            altitude = float(parts[9]) if parts[9] else 0.0

            # HDOP
            hdop = float(parts[8]) if parts[8] else 99.9

            # Number of satellites
            num_sats = int(parts[7]) if parts[7] else 0

            return {
                'fix_quality': fix_quality,
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'hdop': hdop,
                'num_sats': num_sats,
            }

        except (ValueError, IndexError) as e:
            self.get_logger().debug(f'GGA parse error: {e}')
            return None

    def _publish(self):
        """Publish latest GPS fix."""
        with self._lock:
            fix = self._latest_fix
            self._latest_fix = None

        if fix is None:
            return

        # NavSatFix
        msg = NavSatFix()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id

        status_val, quality_str = self.FIX_QUALITY.get(
            fix['fix_quality'],
            (NavSatStatus.STATUS_NO_FIX, f"Unknown ({fix['fix_quality']})")
        )
        msg.status.status = status_val
        msg.status.service = NavSatStatus.SERVICE_GPS

        msg.latitude = fix['latitude']
        msg.longitude = fix['longitude']
        msg.altitude = fix['altitude']

        # Covariance from HDOP (approximate)
        hdop = fix['hdop']
        horiz_cov = (hdop * 0.02) ** 2  # ~2cm base accuracy * HDOP for RTK
        msg.position_covariance[0] = horiz_cov
        msg.position_covariance[4] = horiz_cov
        msg.position_covariance[8] = horiz_cov * 4  # Vertical is worse
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_APPROXIMATED

        self._fix_pub.publish(msg)

        # HDOP
        hdop_msg = Float32()
        hdop_msg.data = hdop
        self._hdop_pub.publish(hdop_msg)

        # Fix quality string
        quality_msg = String()
        quality_msg.data = f'{quality_str} (sats: {fix["num_sats"]})'
        self._quality_pub.publish(quality_msg)

    def _rtcm_bin_cb(self, msg: UInt8MultiArray):
        """Forward binary RTCM corrections from ntrip_client to GPS receiver."""
        if self._rtcm_ser is not None and self._rtcm_ser.is_open:
            try:
                self._rtcm_ser.write(bytes(msg.data))
            except Exception as e:
                self.get_logger().debug(f'RTCM write error: {e}')

    def _rtcm_cb(self, msg: String):
        """Forward legacy string-encoded RTCM corrections to GPS receiver."""
        if self._rtcm_ser is not None and self._rtcm_ser.is_open:
            try:
                self._rtcm_ser.write(msg.data.encode('latin-1'))
            except Exception as e:
                self.get_logger().debug(f'RTCM write error: {e}')

    def destroy_node(self):
        self._running = False
        if hasattr(self, '_read_thread'):
            self._read_thread.join(timeout=2.0)
        try:
            self._ser.close()
        except Exception:
            pass
        if self._rtcm_ser is not None:
            try:
                self._rtcm_ser.close()
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GPSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
