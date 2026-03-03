"""ROS2 bridge service -- wraps rclpy and falls back to mock mode when unavailable.

Supports two operating modes:

* **Real mode** -- creates an rclpy node (``dashboard_bridge``) that subscribes to
  live ROS2 topics, calls services, and publishes paint commands.  ``rclpy.spin()``
  runs in a dedicated daemon thread while an asyncio task reads shared state and
  broadcasts to WebSocket clients at ~5 Hz.

* **Mock mode** -- simulates robot telemetry purely in asyncio so the dashboard
  can be developed and demonstrated without ROS2 or hardware.

Mode is auto-detected (``import rclpy``) but can be forced via the
``MOCK_MODE=1`` environment variable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import threading
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket

from ..models.schemas import GeoPoint, JobStatus, RobotState, RobotStatus

logger = logging.getLogger("ros_bridge")

# ---------------------------------------------------------------------------
# Conditional rclpy import
# ---------------------------------------------------------------------------
_force_mock = os.environ.get("MOCK_MODE", "0").strip() in ("1", "true", "yes")

ROS_AVAILABLE = False
if not _force_mock:
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import (
            QoSProfile,
            ReliabilityPolicy,
            HistoryPolicy,
            DurabilityPolicy,
        )

        # Standard message types
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import NavSatFix
        from geometry_msgs.msg import Twist

        # Striper custom messages / services
        from striper_msgs.msg import JobStatus as JobStatusMsg
        from striper_msgs.msg import SafetyStatus as SafetyStatusMsg
        from striper_msgs.msg import PaintCommand as PaintCommandMsg
        from striper_msgs.srv import StartJob as StartJobSrv
        from striper_msgs.srv import PauseJob as PauseJobSrv
        from striper_msgs.srv import LoadJob as LoadJobSrv

        ROS_AVAILABLE = True
    except ImportError:
        ROS_AVAILABLE = False

if not ROS_AVAILABLE:
    logger.info("rclpy not available or MOCK_MODE forced -- running in mock mode")
else:
    logger.info("rclpy detected -- running in real ROS2 mode")


# ---------------------------------------------------------------------------
# QoS helpers (only meaningful when rclpy is present)
# ---------------------------------------------------------------------------
def _sensor_qos() -> Any:
    """Best-effort QoS suitable for high-frequency sensor data."""
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        durability=DurabilityPolicy.VOLATILE,
    )


def _reliable_qos() -> Any:
    """Reliable QoS for state topics that must not be missed."""
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        durability=DurabilityPolicy.VOLATILE,
    )


# ---------------------------------------------------------------------------
# ROS2 Node (only instantiated when rclpy is available)
# ---------------------------------------------------------------------------
if ROS_AVAILABLE:

    class DashboardBridgeNode(Node):  # type: ignore[misc]
        """rclpy ``Node`` that bridges ROS2 topics/services to the dashboard."""

        def __init__(self) -> None:
            super().__init__("dashboard_bridge")
            self.get_logger().info("DashboardBridgeNode starting up")

            # Shared state -- protected by ``_lock``
            self._lock = threading.Lock()
            self._latest_job_status: Optional[Any] = None
            self._latest_safety: Optional[Any] = None
            self._latest_odom: Optional[Any] = None
            self._latest_navsat: Optional[Any] = None

            # ---- Subscriptions ------------------------------------------------
            self._sub_job_status = self.create_subscription(
                JobStatusMsg,
                "/job_status",
                self._on_job_status,
                _reliable_qos(),
            )
            self._sub_safety = self.create_subscription(
                SafetyStatusMsg,
                "/safety_status",
                self._on_safety_status,
                _reliable_qos(),
            )
            self._sub_odom = self.create_subscription(
                Odometry,
                "/odom",
                self._on_odom,
                _sensor_qos(),
            )
            self._sub_navsat = self.create_subscription(
                NavSatFix,
                "/navsat_fix",
                self._on_navsat,
                _sensor_qos(),
            )

            # ---- Publisher ----------------------------------------------------
            self._pub_paint_cmd = self.create_publisher(
                PaintCommandMsg,
                "/paint_command",
                _reliable_qos(),
            )

            # Also publish zero-velocity Twist for e-stop
            self._pub_cmd_vel = self.create_publisher(
                Twist,
                "/cmd_vel",
                _reliable_qos(),
            )

            # ---- Service clients ----------------------------------------------
            self._cli_start_job = self.create_client(StartJobSrv, "/start_job")
            self._cli_pause_job = self.create_client(PauseJobSrv, "/pause_job")
            self._cli_load_job = self.create_client(LoadJobSrv, "/load_job")

            self.get_logger().info("DashboardBridgeNode ready")

        # -- Subscription callbacks (run inside rclpy spin thread) ---------------

        def _on_job_status(self, msg: Any) -> None:
            with self._lock:
                self._latest_job_status = msg

        def _on_safety_status(self, msg: Any) -> None:
            with self._lock:
                self._latest_safety = msg

        def _on_odom(self, msg: Any) -> None:
            with self._lock:
                self._latest_odom = msg

        def _on_navsat(self, msg: Any) -> None:
            with self._lock:
                self._latest_navsat = msg

        # -- Read snapshot of latest data (called from asyncio thread) ----------

        def read_state(self) -> dict[str, Any]:
            """Return a snapshot of the latest ROS2 data (thread-safe)."""
            with self._lock:
                return {
                    "job_status": self._latest_job_status,
                    "safety": self._latest_safety,
                    "odom": self._latest_odom,
                    "navsat": self._latest_navsat,
                }

        # -- Publishing helpers --------------------------------------------------

        def publish_paint_command(self, spray_on: bool, flow_rate: float) -> None:
            msg = PaintCommandMsg()
            msg.spray_on = spray_on
            msg.flow_rate = flow_rate
            self._pub_paint_cmd.publish(msg)
            self.get_logger().info(
                f"Published PaintCommand: spray_on={spray_on}, flow_rate={flow_rate}"
            )

        def publish_zero_velocity(self) -> None:
            """Publish an all-zero Twist to immediately halt the robot."""
            msg = Twist()
            self._pub_cmd_vel.publish(msg)
            self.get_logger().info("Published zero-velocity Twist (e-stop)")

        # -- Service call helpers (blocking -- called from asyncio via executor) -

        def call_start_job(self, job_id: str, timeout_sec: float = 5.0) -> dict[str, Any]:
            if not self._cli_start_job.wait_for_service(timeout_sec=timeout_sec):
                return {"ok": False, "message": "StartJob service not available"}
            req = StartJobSrv.Request()
            req.job_id = job_id
            future = self._cli_start_job.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_sec)
            if future.result() is not None:
                resp = future.result()
                return {"ok": resp.success, "message": resp.message}
            return {"ok": False, "message": "StartJob service call timed out"}

        def call_pause_job(
            self, job_id: str, resume: bool = False, timeout_sec: float = 5.0
        ) -> dict[str, Any]:
            if not self._cli_pause_job.wait_for_service(timeout_sec=timeout_sec):
                return {"ok": False, "message": "PauseJob service not available"}
            req = PauseJobSrv.Request()
            req.job_id = job_id
            req.resume = resume
            future = self._cli_pause_job.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_sec)
            if future.result() is not None:
                resp = future.result()
                return {"ok": resp.success, "message": resp.message}
            return {"ok": False, "message": "PauseJob service call timed out"}

        def call_load_job(
            self, job_id: str, job_data_json: str, timeout_sec: float = 5.0
        ) -> dict[str, Any]:
            if not self._cli_load_job.wait_for_service(timeout_sec=timeout_sec):
                return {"ok": False, "message": "LoadJob service not available"}
            req = LoadJobSrv.Request()
            req.job_id = job_id
            req.job_data_json = job_data_json
            future = self._cli_load_job.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_sec)
            if future.result() is not None:
                resp = future.result()
                return {"ok": resp.success, "message": resp.message}
            return {"ok": False, "message": "LoadJob service call timed out"}


# ---------------------------------------------------------------------------
# Main bridge class
# ---------------------------------------------------------------------------

class RosBridge:
    """Interface between the dashboard and the ROS2 stack.

    When rclpy is not installed (or ``MOCK_MODE`` is set) the bridge operates
    in *mock mode*, simulating robot telemetry so the dashboard can be
    developed without hardware.
    """

    def __init__(self) -> None:
        self._mock = not ROS_AVAILABLE
        self._ws_clients: list[WebSocket] = []
        self._status = RobotStatus(
            state=RobotState.IDLE,
            position=GeoPoint(lat=30.2672, lng=-97.7431),
            speed=0.0,
            heading=0.0,
            battery=95.0,
            paint_level=87.0,
            gps_accuracy=0.02,
        )
        self._running = False
        self._sim_task: Optional[asyncio.Task[None]] = None
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._current_job_id: Optional[int] = None
        self._job_progress: float = 0.0

        # Real-mode fields
        self._node: Optional[Any] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._executor: Optional[Any] = None
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the bridge.  In mock mode this launches the simulation loop;
        in real mode it initializes rclpy and begins spinning."""
        self._running = True
        self._event_loop = asyncio.get_running_loop()

        if self._mock:
            logger.info("Starting mock simulation loop")
            self._sim_task = asyncio.create_task(self._mock_loop())
        else:
            logger.info("Starting real ROS2 bridge")
            self._start_ros()
            self._broadcast_task = asyncio.create_task(self._ros_broadcast_loop())
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self) -> None:
        """Shut down the bridge cleanly."""
        self._running = False

        # Cancel asyncio tasks
        for task in (self._sim_task, self._broadcast_task, self._reconnect_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Tear down rclpy
        self._shutdown_ros()

    # ------------------------------------------------------------------
    # ROS2 lifecycle helpers
    # ------------------------------------------------------------------

    def _start_ros(self) -> None:
        """Initialize rclpy, create the node, and start the spin thread."""
        try:
            if not rclpy.ok():
                rclpy.init()
        except Exception:
            # rclpy.init() may already have been called; that is fine.
            try:
                rclpy.init()
            except RuntimeError:
                pass

        self._node = DashboardBridgeNode()
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        self._spin_thread = threading.Thread(
            target=self._spin_worker, daemon=True, name="rclpy-spin"
        )
        self._spin_thread.start()
        logger.info("rclpy spin thread started")

    def _spin_worker(self) -> None:
        """Target for the daemon thread -- spins the executor until shutdown."""
        try:
            while self._running and rclpy.ok():
                self._executor.spin_once(timeout_sec=0.1)
        except Exception:
            logger.exception("rclpy spin thread encountered an error")
        finally:
            logger.info("rclpy spin thread exiting")

    def _shutdown_ros(self) -> None:
        """Destroy the node and shut down rclpy."""
        if self._executor is not None:
            try:
                self._executor.shutdown()
            except Exception:
                pass
            self._executor = None

        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._node = None

        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None

        logger.info("ROS2 shutdown complete")

    # ------------------------------------------------------------------
    # Real-mode: broadcast loop (runs on asyncio event loop)
    # ------------------------------------------------------------------

    async def _ros_broadcast_loop(self) -> None:
        """Read latest ROS2 data from the node at ~5 Hz and push to WS clients."""
        while self._running:
            await asyncio.sleep(0.2)

            if self._node is None:
                continue

            try:
                snapshot = self._node.read_state()
                self._apply_ros_snapshot(snapshot)
            except Exception:
                logger.exception("Error reading ROS2 state")
                continue

            self._status.timestamp = datetime.now().isoformat()
            await self._broadcast(
                {
                    "event": "status",
                    "data": json.loads(self._status.model_dump_json()),
                }
            )

    def _apply_ros_snapshot(self, snap: dict[str, Any]) -> None:
        """Convert raw ROS2 message data into the Pydantic ``RobotStatus`` model."""

        # --- JobStatus --------------------------------------------------
        job_msg = snap.get("job_status")
        if job_msg is not None:
            state_map = {
                0: RobotState.IDLE,      # IDLE
                1: RobotState.RUNNING,   # RUNNING
                2: RobotState.PAUSED,    # PAUSED
                3: RobotState.IDLE,      # COMPLETE
                4: RobotState.ERROR,     # ERROR
            }
            self._status.state = state_map.get(job_msg.state, RobotState.IDLE)
            self._status.job_progress = float(job_msg.progress)
            if job_msg.job_id:
                try:
                    self._status.current_job_id = int(job_msg.job_id)
                except (ValueError, TypeError):
                    self._status.current_job_id = None

        # --- SafetyStatus -----------------------------------------------
        safety_msg = snap.get("safety")
        if safety_msg is not None:
            if safety_msg.estop_active:
                self._status.state = RobotState.ESTOPPED

        # --- Odometry ---------------------------------------------------
        odom_msg = snap.get("odom")
        if odom_msg is not None:
            twist = odom_msg.twist.twist
            linear_speed = math.sqrt(
                twist.linear.x ** 2 + twist.linear.y ** 2
            )
            self._status.speed = round(linear_speed, 3)

            # Derive heading from orientation quaternion
            q = odom_msg.pose.pose.orientation
            # yaw from quaternion
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw_rad = math.atan2(siny_cosp, cosy_cosp)
            self._status.heading = round(math.degrees(yaw_rad) % 360, 1)

        # --- NavSatFix (GPS) -------------------------------------------
        navsat_msg = snap.get("navsat")
        if navsat_msg is not None:
            self._status.position = GeoPoint(
                lat=navsat_msg.latitude,
                lng=navsat_msg.longitude,
            )
            # Use the position covariance diagonal as a rough accuracy proxy
            if (
                navsat_msg.position_covariance
                and len(navsat_msg.position_covariance) >= 5
            ):
                horiz_var = (
                    navsat_msg.position_covariance[0]
                    + navsat_msg.position_covariance[4]
                ) / 2.0
                self._status.gps_accuracy = round(math.sqrt(max(horiz_var, 0.0)), 4)

    # ------------------------------------------------------------------
    # Reconnection loop (real mode)
    # ------------------------------------------------------------------

    async def _reconnect_loop(self) -> None:
        """Monitor the rclpy spin thread; restart if it dies."""
        while self._running:
            await asyncio.sleep(3.0)

            if self._node is None:
                continue

            # Check if the spin thread is still alive
            if self._spin_thread is not None and not self._spin_thread.is_alive():
                logger.warning(
                    "rclpy spin thread died -- attempting to reconnect"
                )
                self._status.state = RobotState.DISCONNECTED

                self._shutdown_ros()
                await asyncio.sleep(2.0)

                if self._running:
                    try:
                        self._start_ros()
                        logger.info("Reconnected to ROS2")
                    except Exception:
                        logger.exception("Failed to reconnect to ROS2")

    # ------------------------------------------------------------------
    # WebSocket management
    # ------------------------------------------------------------------

    async def register_ws(self, ws: WebSocket) -> None:
        self._ws_clients.append(ws)

    async def unregister_ws(self, ws: WebSocket) -> None:
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    async def _broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_status(self) -> RobotStatus:
        return self._status.model_copy()

    async def start_job(self, job_id: int) -> dict[str, Any]:
        if not self._mock and self._node is not None:
            # Call the ROS2 service in a thread-pool executor to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._node.call_start_job,
                str(job_id),
            )
            if result.get("ok"):
                self._current_job_id = job_id
                self._job_progress = 0.0
                self._status.state = RobotState.RUNNING
                self._status.current_job_id = job_id
                self._status.job_progress = 0.0
                await self._broadcast({"event": "job_started", "job_id": job_id})
            return result

        # Mock mode
        self._current_job_id = job_id
        self._job_progress = 0.0
        self._status.state = RobotState.RUNNING
        self._status.current_job_id = job_id
        self._status.job_progress = 0.0
        await self._broadcast({"event": "job_started", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} started"}

    async def pause_job(self, job_id: int) -> dict[str, Any]:
        if not self._mock and self._node is not None:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._node.call_pause_job,
                str(job_id),
                False,
            )
            if result.get("ok"):
                self._status.state = RobotState.PAUSED
                await self._broadcast({"event": "job_paused", "job_id": job_id})
            return result

        # Mock mode
        self._status.state = RobotState.PAUSED
        await self._broadcast({"event": "job_paused", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} paused"}

    async def stop_job(self, job_id: int) -> dict[str, Any]:
        if not self._mock and self._node is not None:
            loop = asyncio.get_running_loop()
            # Use PauseJob with the intention of stopping; alternatively
            # the caller may cancel the action goal.  For now we call
            # pause and reset local state.
            result = await loop.run_in_executor(
                None,
                self._node.call_pause_job,
                str(job_id),
                False,
            )
            self._status.state = RobotState.IDLE
            self._status.speed = 0.0
            self._status.current_job_id = None
            self._status.job_progress = 0.0
            self._current_job_id = None
            self._job_progress = 0.0
            await self._broadcast({"event": "job_stopped", "job_id": job_id})
            return {"ok": True, "message": f"Job {job_id} stopped"}

        # Mock mode
        self._status.state = RobotState.IDLE
        self._status.speed = 0.0
        self._status.current_job_id = None
        self._status.job_progress = 0.0
        self._current_job_id = None
        self._job_progress = 0.0
        await self._broadcast({"event": "job_stopped", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} stopped"}

    async def load_job(self, job_id: int, job_data_json: str) -> dict[str, Any]:
        """Send job data to the ROS2 LoadJob service."""
        if not self._mock and self._node is not None:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._node.call_load_job,
                str(job_id),
                job_data_json,
            )
            return result

        # Mock mode
        return {"ok": True, "message": f"Job {job_id} loaded (mock)"}

    async def paint_command(self, spray_on: bool, flow_rate: float) -> dict[str, Any]:
        """Publish a manual paint test command."""
        if not self._mock and self._node is not None:
            self._node.publish_paint_command(spray_on, flow_rate)
            return {
                "ok": True,
                "message": f"PaintCommand published: spray_on={spray_on}, flow_rate={flow_rate}",
            }

        # Mock mode
        return {
            "ok": True,
            "message": f"PaintCommand (mock): spray_on={spray_on}, flow_rate={flow_rate}",
        }

    async def estop(self) -> dict[str, Any]:
        if not self._mock and self._node is not None:
            # Immediately publish zero velocity
            self._node.publish_zero_velocity()
            logger.warning("E-STOP activated -- zero velocity published")

        self._status.state = RobotState.ESTOPPED
        self._status.speed = 0.0
        await self._broadcast({"event": "estop_activated"})
        return {"ok": True, "message": "E-Stop activated"}

    async def release_estop(self) -> dict[str, Any]:
        self._status.state = RobotState.IDLE
        await self._broadcast({"event": "estop_released"})
        return {"ok": True, "message": "E-Stop released"}

    # ------------------------------------------------------------------
    # Mock simulation loop (unchanged from original)
    # ------------------------------------------------------------------

    async def _mock_loop(self) -> None:
        """Simulate robot telemetry at ~5 Hz."""
        t = 0.0
        base_lat = self._status.position.lat if self._status.position else 30.2672
        base_lng = self._status.position.lng if self._status.position else -97.7431

        while self._running:
            await asyncio.sleep(0.2)
            t += 0.2

            if self._status.state == RobotState.RUNNING:
                # Simulate driving a stripe pattern
                self._status.speed = 1.2 + random.uniform(-0.1, 0.1)
                self._status.heading = (self._status.heading + 0.5) % 360
                offset_lat = 0.0001 * math.sin(t * 0.3)
                offset_lng = 0.0001 * math.cos(t * 0.3)
                self._status.position = GeoPoint(
                    lat=base_lat + offset_lat,
                    lng=base_lng + offset_lng,
                )
                self._status.battery = max(0, self._status.battery - 0.002)
                self._status.paint_level = max(0, self._status.paint_level - 0.003)
                self._job_progress = min(100.0, self._job_progress + 0.15)
                self._status.job_progress = round(self._job_progress, 1)
                self._status.gps_accuracy = 0.02 + random.uniform(-0.005, 0.005)

                if self._job_progress >= 100.0:
                    self._status.state = RobotState.IDLE
                    self._status.speed = 0.0
                    self._status.current_job_id = None
                    await self._broadcast({
                        "event": "job_completed",
                        "job_id": self._current_job_id,
                    })
                    self._current_job_id = None
                    self._job_progress = 0.0

            elif self._status.state == RobotState.IDLE:
                self._status.speed = 0.0
                self._status.gps_accuracy = 0.02 + random.uniform(-0.003, 0.003)

            self._status.timestamp = datetime.now().isoformat()
            await self._broadcast({
                "event": "status",
                "data": json.loads(self._status.model_dump_json()),
            })


# Singleton instance
ros_bridge = RosBridge()
