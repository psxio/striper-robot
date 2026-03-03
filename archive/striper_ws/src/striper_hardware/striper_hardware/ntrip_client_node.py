"""NTRIP client node for RTK GPS corrections.

Connects to an NTRIP caster to receive RTCM3 correction data for the
ZED-F9P GPS receiver. Sends periodic GGA position reports to the caster
and either publishes corrections on a ROS topic or writes them directly
to a serial port connected to the GPS module.

Typical NTRIP casters:
  - rtk2go.com (free, community)
  - UNAVCO / state DOT CORS networks
  - Emlid Caster, Lefebure, etc.
"""

import base64
import socket
import threading
import time

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix
from std_msgs.msg import UInt8MultiArray

try:
    import serial
    _HAS_SERIAL = True
except ImportError:
    _HAS_SERIAL = False


class NtripClientNode(Node):
    """ROS2 node that streams RTCM3 corrections from an NTRIP caster."""

    def __init__(self):
        super().__init__('ntrip_client')

        # -----------------------------------------------------------------
        # Parameters
        # -----------------------------------------------------------------
        self.declare_parameter('ntrip_host', 'rtk2go.com')
        self.declare_parameter('ntrip_port', 2101)
        self.declare_parameter('ntrip_mountpoint', '')
        self.declare_parameter('ntrip_username', '')
        self.declare_parameter('ntrip_password', '')
        self.declare_parameter('serial_output_port', '')
        self.declare_parameter('serial_output_baud', 115200)
        self.declare_parameter('gga_update_interval', 10.0)
        self.declare_parameter('reconnect_delay', 5.0)
        self.declare_parameter('recv_timeout', 10.0)

        self._host = self.get_parameter('ntrip_host').value
        self._port = self.get_parameter('ntrip_port').value
        self._mountpoint = self.get_parameter('ntrip_mountpoint').value
        self._username = self.get_parameter('ntrip_username').value
        self._password = self.get_parameter('ntrip_password').value
        self._serial_port = self.get_parameter('serial_output_port').value
        self._serial_baud = self.get_parameter('serial_output_baud').value
        self._gga_interval = self.get_parameter('gga_update_interval').value
        self._reconnect_delay = self.get_parameter('reconnect_delay').value
        self._recv_timeout = self.get_parameter('recv_timeout').value

        if not self._mountpoint:
            self.get_logger().error(
                'ntrip_mountpoint parameter is required but was not set. '
                'Node will not connect.'
            )

        # -----------------------------------------------------------------
        # Serial output (direct connection to ZED-F9P correction port)
        # -----------------------------------------------------------------
        self._serial_out = None
        if self._serial_port:
            if _HAS_SERIAL:
                try:
                    self._serial_out = serial.Serial(
                        self._serial_port, self._serial_baud, timeout=0.1
                    )
                    self.get_logger().info(
                        f'RTCM serial output opened: {self._serial_port} '
                        f'@ {self._serial_baud}'
                    )
                except serial.SerialException as e:
                    self.get_logger().error(
                        f'Failed to open RTCM serial output {self._serial_port}: {e}. '
                        f'Will publish to topic instead.'
                    )
            else:
                self.get_logger().warn(
                    'pyserial not installed; cannot use serial_output_port. '
                    'Will publish to topic instead.'
                )

        # -----------------------------------------------------------------
        # ROS publishers / subscribers
        # -----------------------------------------------------------------
        self._rtcm_pub = self.create_publisher(
            UInt8MultiArray, 'rtcm_corrections', 10
        )

        self._navsat_sub = self.create_subscription(
            NavSatFix, 'gps/fix', self._navsat_cb, 10
        )

        # -----------------------------------------------------------------
        # State
        # -----------------------------------------------------------------
        self._latest_gga = ''
        self._latest_lat = 0.0
        self._latest_lon = 0.0
        self._latest_alt = 0.0
        self._gga_lock = threading.Lock()

        self._socket = None
        self._connected = False
        self._running = True
        self._total_bytes = 0
        self._last_rtcm_time = 0.0

        # -----------------------------------------------------------------
        # Background connection thread
        # -----------------------------------------------------------------
        self._conn_thread = threading.Thread(
            target=self._connection_loop, daemon=True
        )
        self._conn_thread.start()

        # -----------------------------------------------------------------
        # Status logging timer (every 30 seconds)
        # -----------------------------------------------------------------
        self._status_timer = self.create_timer(30.0, self._log_status)

        self.get_logger().info(
            f'NTRIP client node started: {self._host}:{self._port}/{self._mountpoint}'
        )

    # =====================================================================
    # NavSatFix callback -- build GGA sentence for NTRIP caster
    # =====================================================================

    def _navsat_cb(self, msg: NavSatFix):
        """Store latest position and build a GGA sentence for the caster."""
        lat = msg.latitude
        lon = msg.longitude
        alt = msg.altitude

        if lat == 0.0 and lon == 0.0:
            return

        gga = self._build_gga(lat, lon, alt)
        with self._gga_lock:
            self._latest_gga = gga
            self._latest_lat = lat
            self._latest_lon = lon
            self._latest_alt = alt

    @staticmethod
    def _build_gga(lat: float, lon: float, alt: float) -> str:
        """Build a minimal NMEA GGA sentence from decimal-degree coordinates.

        The GGA sentence is used by the NTRIP caster to select the nearest
        base station and to verify that the rover is within range.
        """
        # Convert decimal degrees to NMEA DDMM.MMMMM format
        lat_dir = 'N' if lat >= 0 else 'S'
        lat = abs(lat)
        lat_deg = int(lat)
        lat_min = (lat - lat_deg) * 60.0
        lat_nmea = f'{lat_deg:02d}{lat_min:08.5f}'

        lon_dir = 'E' if lon >= 0 else 'W'
        lon = abs(lon)
        lon_deg = int(lon)
        lon_min = (lon - lon_deg) * 60.0
        lon_nmea = f'{lon_deg:03d}{lon_min:08.5f}'

        # Use current UTC time
        utc = time.gmtime()
        time_str = f'{utc.tm_hour:02d}{utc.tm_min:02d}{utc.tm_sec:02d}.00'

        # Build the sentence (fix quality=1, 12 sats, HDOP=1.0)
        body = (
            f'GPGGA,{time_str},{lat_nmea},{lat_dir},'
            f'{lon_nmea},{lon_dir},1,12,1.0,{alt:.1f},M,0.0,M,,'
        )

        # Compute NMEA checksum (XOR of all chars between $ and *)
        checksum = 0
        for ch in body:
            checksum ^= ord(ch)

        return f'${body}*{checksum:02X}\r\n'

    # =====================================================================
    # NTRIP connection loop (runs in background thread)
    # =====================================================================

    def _connection_loop(self):
        """Continuously connect to NTRIP caster and read RTCM data."""
        while self._running:
            if not self._mountpoint:
                time.sleep(self._reconnect_delay)
                continue

            try:
                self._connect()
                self._stream_rtcm()
            except Exception as e:
                self.get_logger().warn(f'NTRIP connection error: {e}')

            # Clean up socket
            self._disconnect()

            if self._running:
                self.get_logger().info(
                    f'Reconnecting to NTRIP caster in {self._reconnect_delay}s...'
                )
                time.sleep(self._reconnect_delay)

    def _connect(self):
        """Establish connection to the NTRIP caster."""
        self.get_logger().info(
            f'Connecting to {self._host}:{self._port}/{self._mountpoint}...'
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._recv_timeout)
        sock.connect((self._host, self._port))

        # Build HTTP request
        # NTRIP v1 uses HTTP/1.0 GET with basic auth
        auth = ''
        if self._username:
            credentials = f'{self._username}:{self._password}'
            encoded = base64.b64encode(credentials.encode()).decode()
            auth = f'Authorization: Basic {encoded}\r\n'

        # Include initial GGA if we have one
        gga_header = ''
        with self._gga_lock:
            if self._latest_gga:
                gga_header = f'Ntrip-GGA: {self._latest_gga.strip()}\r\n'

        request = (
            f'GET /{self._mountpoint} HTTP/1.0\r\n'
            f'Host: {self._host}\r\n'
            f'User-Agent: NTRIP StriperRobot/1.0\r\n'
            f'Accept: */*\r\n'
            f'{auth}'
            f'{gga_header}'
            f'Connection: close\r\n'
            f'\r\n'
        )

        sock.sendall(request.encode())

        # Read response header
        response = b''
        while b'\r\n\r\n' not in response:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError('Connection closed during header read')
            response += chunk

        header_end = response.index(b'\r\n\r\n') + 4
        header = response[:header_end].decode('ascii', errors='ignore')

        # Check for ICY 200 OK or HTTP/1.x 200
        first_line = header.split('\r\n')[0]
        if '200' not in first_line:
            raise ConnectionError(
                f'NTRIP caster rejected connection: {first_line}'
            )

        self.get_logger().info(f'NTRIP connected: {first_line}')

        # Any remaining data after the header is RTCM data
        leftover = response[header_end:]
        if leftover:
            self._handle_rtcm(leftover)

        self._socket = sock
        self._connected = True

    def _stream_rtcm(self):
        """Read RTCM data from the socket and forward it."""
        last_gga_send = 0.0

        while self._running and self._connected:
            # Send GGA update periodically
            now = time.monotonic()
            if now - last_gga_send >= self._gga_interval:
                self._send_gga()
                last_gga_send = now

            # Read RTCM data
            try:
                data = self._socket.recv(4096)
                if not data:
                    self.get_logger().warn('NTRIP caster closed connection')
                    self._connected = False
                    break
                self._handle_rtcm(data)
            except socket.timeout:
                self.get_logger().warn(
                    f'No data from NTRIP caster for {self._recv_timeout}s'
                )
                # Don't disconnect immediately -- caster may be slow
                continue
            except (ConnectionError, OSError) as e:
                self.get_logger().warn(f'NTRIP receive error: {e}')
                self._connected = False
                break

    def _send_gga(self):
        """Send GGA position to the NTRIP caster."""
        with self._gga_lock:
            gga = self._latest_gga

        if not gga or not self._socket:
            return

        try:
            self._socket.sendall(gga.encode())
            self.get_logger().debug(f'Sent GGA to caster: {gga.strip()}')
        except (OSError, socket.error) as e:
            self.get_logger().warn(f'Failed to send GGA: {e}')
            self._connected = False

    def _handle_rtcm(self, data: bytes):
        """Process received RTCM data: publish to topic and/or serial."""
        self._total_bytes += len(data)
        self._last_rtcm_time = time.monotonic()

        # Publish on ROS topic
        msg = UInt8MultiArray()
        msg.data = list(data)
        self._rtcm_pub.publish(msg)

        # Write to serial port if configured
        if self._serial_out is not None:
            try:
                self._serial_out.write(data)
            except Exception as e:
                self.get_logger().debug(f'Serial RTCM write error: {e}')

    def _disconnect(self):
        """Close the NTRIP socket."""
        self._connected = False
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    # =====================================================================
    # Status logging
    # =====================================================================

    def _log_status(self):
        """Periodically log connection status and stats."""
        if self._connected:
            age = time.monotonic() - self._last_rtcm_time if self._last_rtcm_time else float('inf')
            self.get_logger().info(
                f'NTRIP status: connected to {self._host}/{self._mountpoint} | '
                f'Total RTCM bytes: {self._total_bytes} | '
                f'Correction age: {age:.1f}s'
            )
        else:
            self.get_logger().warn(
                f'NTRIP status: DISCONNECTED from {self._host}/{self._mountpoint} | '
                f'Total RTCM bytes received so far: {self._total_bytes}'
            )

    # =====================================================================
    # Shutdown
    # =====================================================================

    def destroy_node(self):
        self._running = False
        self._disconnect()
        if hasattr(self, '_conn_thread'):
            self._conn_thread.join(timeout=3.0)
        if self._serial_out is not None:
            try:
                self._serial_out.close()
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = NtripClientNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
