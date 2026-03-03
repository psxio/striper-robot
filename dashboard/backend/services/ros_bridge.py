"""ROS2 bridge service — wraps rclpy and falls back to mock mode when unavailable."""

import asyncio
import json
import math
import random
import time
from typing import Any, Optional

from fastapi import WebSocket

from ..models.schemas import GeoPoint, JobStatus, RobotState, RobotStatus

# Try importing rclpy; if unavailable we run in mock mode.
try:
    import rclpy  # noqa: F401
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


class RosBridge:
    """Interface between the dashboard and the ROS2 stack.

    When rclpy is not installed the bridge operates in *mock mode*, simulating
    robot telemetry so the dashboard can be developed without hardware.
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
        self._current_job_id: Optional[int] = None
        self._job_progress: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        if self._mock:
            self._sim_task = asyncio.create_task(self._mock_loop())

    async def stop(self) -> None:
        self._running = False
        if self._sim_task:
            self._sim_task.cancel()
            try:
                await self._sim_task
            except asyncio.CancelledError:
                pass

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
        self._current_job_id = job_id
        self._job_progress = 0.0
        self._status.state = RobotState.RUNNING
        self._status.current_job_id = job_id
        self._status.job_progress = 0.0
        await self._broadcast({"event": "job_started", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} started"}

    async def pause_job(self, job_id: int) -> dict[str, Any]:
        self._status.state = RobotState.PAUSED
        await self._broadcast({"event": "job_paused", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} paused"}

    async def stop_job(self, job_id: int) -> dict[str, Any]:
        self._status.state = RobotState.IDLE
        self._status.speed = 0.0
        self._status.current_job_id = None
        self._status.job_progress = 0.0
        self._current_job_id = None
        self._job_progress = 0.0
        await self._broadcast({"event": "job_stopped", "job_id": job_id})
        return {"ok": True, "message": f"Job {job_id} stopped"}

    async def estop(self) -> dict[str, Any]:
        self._status.state = RobotState.ESTOPPED
        self._status.speed = 0.0
        await self._broadcast({"event": "estop_activated"})
        return {"ok": True, "message": "E-Stop activated"}

    async def release_estop(self) -> dict[str, Any]:
        self._status.state = RobotState.IDLE
        await self._broadcast({"event": "estop_released"})
        return {"ok": True, "message": "E-Stop released"}

    # ------------------------------------------------------------------
    # Mock simulation loop
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

            from datetime import datetime
            self._status.timestamp = datetime.now().isoformat()
            await self._broadcast({
                "event": "status",
                "data": json.loads(self._status.model_dump_json()),
            })


# Singleton instance
ros_bridge = RosBridge()
