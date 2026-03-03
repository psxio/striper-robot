"""Heartbeat watchdog monitor node.

Monitors configurable list of critical nodes by tracking their
heartbeat messages. Triggers safety warnings on timeout and
safety stops on extended timeout.
"""

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool, String


class WatchdogNode(Node):
    """Monitors heartbeats from critical nodes."""

    def __init__(self):
        super().__init__('watchdog')

        # Parameters
        self.declare_parameter('monitored_nodes', [
            'motor_driver',
            'gps_node',
            'imu_node',
            'safety_supervisor',
        ])
        self.declare_parameter('heartbeat_timeout', 2.0)    # seconds - warning
        self.declare_parameter('critical_timeout', 5.0)      # seconds - safety stop
        self.declare_parameter('check_rate', 2.0)            # Hz

        self._monitored = self.get_parameter('monitored_nodes').value
        self._heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self._critical_timeout = self.get_parameter('critical_timeout').value

        # Track last heartbeat time for each node
        self._last_heartbeat = {}
        self._node_alive = {}
        self._heartbeat_subs = {}

        for node_name in self._monitored:
            self._last_heartbeat[node_name] = self.get_clock().now()
            self._node_alive[node_name] = True

            # Subscribe to each node's heartbeat topic
            topic = f'/heartbeat/{node_name}'
            self._heartbeat_subs[node_name] = self.create_subscription(
                Bool,
                topic,
                lambda msg, name=node_name: self._heartbeat_cb(msg, name),
                10,
            )

        # Publishers
        self._timeout_pub = self.create_publisher(Bool, 'safety/watchdog_timeout', 10)
        self._status_pub = self.create_publisher(String, 'watchdog/status', 10)

        # Check timer
        rate = self.get_parameter('check_rate').value
        self._timer = self.create_timer(1.0 / rate, self._check_heartbeats)

        self.get_logger().info(
            f'Watchdog monitoring {len(self._monitored)} nodes: '
            f'{", ".join(self._monitored)}'
        )

    def _heartbeat_cb(self, msg: Bool, node_name: str):
        """Update heartbeat timestamp for a node."""
        self._last_heartbeat[node_name] = self.get_clock().now()
        self._node_alive[node_name] = True

    def _check_heartbeats(self):
        """Check all monitored nodes for heartbeat timeouts."""
        now = self.get_clock().now()
        any_timeout = False
        any_critical = False
        dead_nodes = []
        warn_nodes = []

        for node_name in self._monitored:
            elapsed = (now - self._last_heartbeat[node_name]).nanoseconds * 1e-9

            if elapsed > self._critical_timeout:
                any_critical = True
                dead_nodes.append(node_name)
                self._node_alive[node_name] = False
            elif elapsed > self._heartbeat_timeout:
                any_timeout = True
                warn_nodes.append(node_name)

        # Publish timeout flag (true if any critical timeout)
        timeout_msg = Bool()
        timeout_msg.data = any_critical
        self._timeout_pub.publish(timeout_msg)

        # Publish status
        status_msg = String()
        alive = [n for n in self._monitored if self._node_alive[n]]
        parts = []
        if dead_nodes:
            parts.append(f'DEAD: {", ".join(dead_nodes)}')
        if warn_nodes:
            parts.append(f'WARN: {", ".join(warn_nodes)}')
        parts.append(f'ALIVE: {", ".join(alive)}' if alive else 'ALIVE: none')
        status_msg.data = ' | '.join(parts)
        self._status_pub.publish(status_msg)

        if dead_nodes:
            self.get_logger().error(
                f'Nodes unresponsive (>{self._critical_timeout}s): '
                f'{", ".join(dead_nodes)}',
                throttle_duration_sec=5.0,
            )
        if warn_nodes:
            self.get_logger().warn(
                f'Nodes slow (>{self._heartbeat_timeout}s): '
                f'{", ".join(warn_nodes)}',
                throttle_duration_sec=5.0,
            )


def main(args=None):
    rclpy.init(args=args)
    node = WatchdogNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
