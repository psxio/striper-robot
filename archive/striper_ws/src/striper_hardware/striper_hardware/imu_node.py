"""BNO085 IMU driver node.

Reads orientation, angular velocity, and linear acceleration from a
BNO085 IMU via I2C and publishes sensor_msgs/Imu at 100Hz.
"""

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Imu

# Try to import the BNO08x library; fall back to mock
try:
    import board
    import adafruit_bno08x
    from adafruit_bno08x.i2c import BNO08X_I2C
    _HAS_BNO = True
except (ImportError, NotImplementedError, RuntimeError):
    _HAS_BNO = False


class _MockBNO08X:
    """Mock IMU for development without hardware."""

    def enable_feature(self, feature):
        pass

    @property
    def quaternion(self):
        return (0.0, 0.0, 0.0, 1.0)  # x, y, z, w identity

    @property
    def gyro(self):
        return (0.0, 0.0, 0.0)

    @property
    def linear_acceleration(self):
        return (0.0, 0.0, 0.0)

    @property
    def calibration_status(self):
        return 3  # Fully calibrated


class IMUNode(Node):
    """Publishes IMU data from a BNO085 sensor."""

    def __init__(self):
        super().__init__('imu_node')

        # Parameters
        self.declare_parameter('publish_rate', 100.0)  # Hz
        self.declare_parameter('frame_id', 'imu_link')
        self.declare_parameter('i2c_address', 0x4A)

        self._frame_id = self.get_parameter('frame_id').value
        rate = self.get_parameter('publish_rate').value

        # Initialize IMU
        if _HAS_BNO:
            try:
                i2c = board.I2C()
                addr = self.get_parameter('i2c_address').value
                self._imu = BNO08X_I2C(i2c, address=addr)
                self._imu.enable_feature(adafruit_bno08x.BNO_REPORT_ROTATION_VECTOR)
                self._imu.enable_feature(adafruit_bno08x.BNO_REPORT_GYROSCOPE)
                self._imu.enable_feature(adafruit_bno08x.BNO_REPORT_LINEAR_ACCELERATION)
                self.get_logger().info('BNO085 IMU initialized via I2C')
            except Exception as e:
                self.get_logger().error(f'BNO085 init failed: {e}. Using mock.')
                self._imu = _MockBNO08X()
        else:
            self.get_logger().warn('adafruit_bno08x not available; using mock IMU')
            self._imu = _MockBNO08X()

        # Covariance matrices (diagonal, small for a good IMU)
        self._orientation_cov = [0.0] * 9
        self._orientation_cov[0] = 0.0001
        self._orientation_cov[4] = 0.0001
        self._orientation_cov[8] = 0.0001

        self._angular_vel_cov = [0.0] * 9
        self._angular_vel_cov[0] = 0.0002
        self._angular_vel_cov[4] = 0.0002
        self._angular_vel_cov[8] = 0.0002

        self._linear_accel_cov = [0.0] * 9
        self._linear_accel_cov[0] = 0.001
        self._linear_accel_cov[4] = 0.001
        self._linear_accel_cov[8] = 0.001

        # Publisher
        self._imu_pub = self.create_publisher(Imu, 'imu/data', 10)

        # Timer
        self._timer = self.create_timer(1.0 / rate, self._publish_imu)

        self.get_logger().info(f'IMU node ready at {rate} Hz')

    def _publish_imu(self):
        """Read IMU and publish Imu message."""
        try:
            quat = self._imu.quaternion
            gyro = self._imu.gyro
            accel = self._imu.linear_acceleration
        except Exception as e:
            self.get_logger().debug(f'IMU read error: {e}')
            return

        if quat is None or gyro is None or accel is None:
            return

        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id

        # Orientation (BNO08x returns x, y, z, w)
        msg.orientation.x = float(quat[0])
        msg.orientation.y = float(quat[1])
        msg.orientation.z = float(quat[2])
        msg.orientation.w = float(quat[3])
        msg.orientation_covariance = self._orientation_cov

        # Angular velocity (rad/s)
        msg.angular_velocity.x = float(gyro[0])
        msg.angular_velocity.y = float(gyro[1])
        msg.angular_velocity.z = float(gyro[2])
        msg.angular_velocity_covariance = self._angular_vel_cov

        # Linear acceleration (m/s^2, gravity removed)
        msg.linear_acceleration.x = float(accel[0])
        msg.linear_acceleration.y = float(accel[1])
        msg.linear_acceleration.z = float(accel[2])
        msg.linear_acceleration_covariance = self._linear_accel_cov

        self._imu_pub.publish(msg)

        # Periodically log calibration status
        try:
            cal = self._imu.calibration_status
            if cal < 3:
                self.get_logger().warn(
                    f'IMU calibration: {cal}/3', throttle_duration_sec=10.0
                )
        except Exception:
            pass


def main(args=None):
    rclpy.init(args=args)
    node = IMUNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
