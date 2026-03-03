"""Job orchestrator node for the striper robot.

Manages paint job execution by sequencing through paint segments
and sending each as a Nav2 goal via the FollowPath action.
"""

import json
import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped

from striper_msgs.action import ExecutePaintJob
from striper_msgs.msg import JobStatus, PaintSegment, PaintCommand
from striper_msgs.srv import LoadJob, StartJob, PauseJob


class PathManagerNode(Node):
    """Orchestrates paint job execution through Nav2."""

    # State constants matching JobStatus message
    STATE_IDLE = JobStatus.IDLE
    STATE_RUNNING = JobStatus.RUNNING
    STATE_PAUSED = JobStatus.PAUSED
    STATE_COMPLETE = JobStatus.COMPLETE
    STATE_ERROR = JobStatus.ERROR

    def __init__(self):
        super().__init__('path_manager')

        self.declare_parameter('nav2_action_name', 'follow_path')
        self.declare_parameter('status_publish_rate', 2.0)

        self._cb_group = ReentrantCallbackGroup()

        # State
        self._state = self.STATE_IDLE
        self._current_job_id = ''
        self._segments = []
        self._current_segment_idx = 0
        self._total_distance = 0.0
        self._goal_handle = None
        self._nav2_goal_handle = None
        self._loaded_jobs = {}

        # Action server for ExecutePaintJob
        self._action_server = ActionServer(
            self,
            ExecutePaintJob,
            'execute_paint_job',
            execute_callback=self._execute_job_cb,
            goal_callback=self._goal_cb,
            cancel_callback=self._cancel_cb,
            callback_group=self._cb_group,
        )

        # Nav2 FollowPath action client
        nav2_action = self.get_parameter('nav2_action_name').get_parameter_value().string_value
        self._nav2_client = ActionClient(
            self, FollowPath, nav2_action, callback_group=self._cb_group
        )

        # Services
        self._load_srv = self.create_service(
            LoadJob, 'load_job', self._load_job_cb, callback_group=self._cb_group
        )
        self._start_srv = self.create_service(
            StartJob, 'start_job', self._start_job_cb, callback_group=self._cb_group
        )
        self._pause_srv = self.create_service(
            PauseJob, 'pause_job', self._pause_job_cb, callback_group=self._cb_group
        )

        # Publishers
        self._status_pub = self.create_publisher(JobStatus, 'job_status', 10)
        self._paint_cmd_pub = self.create_publisher(PaintCommand, 'paint_command', 10)

        # Status timer
        rate = self.get_parameter('status_publish_rate').get_parameter_value().double_value
        self._status_timer = self.create_timer(1.0 / rate, self._publish_status)

        self.get_logger().info('PathManager node ready')

    def _goal_cb(self, goal_request):
        """Accept or reject incoming job goals."""
        if self._state == self.STATE_RUNNING:
            self.get_logger().warn('Rejecting goal: job already running')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_cb(self, goal_handle):
        """Accept cancel requests."""
        self.get_logger().info('Cancel requested for job')
        return CancelResponse.ACCEPT

    async def _execute_job_cb(self, goal_handle):
        """Execute paint job by sequencing through segments."""
        self._goal_handle = goal_handle
        request = goal_handle.request
        self._current_job_id = request.job_id
        self._segments = list(request.segments)
        self._current_segment_idx = 0
        self._total_distance = 0.0
        self._state = self.STATE_RUNNING

        self.get_logger().info(
            f'Starting job {self._current_job_id} with {len(self._segments)} segments'
        )

        result = ExecutePaintJob.Result()

        # Wait for Nav2 action server
        if not self._nav2_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Nav2 FollowPath action server not available')
            self._state = self.STATE_ERROR
            result.success = False
            result.message = 'Nav2 action server not available'
            goal_handle.abort()
            return result

        for idx, segment in enumerate(self._segments):
            self._current_segment_idx = idx

            # Check for cancellation
            if goal_handle.is_cancel_requested:
                self._stop_paint()
                self._state = self.STATE_IDLE
                result.success = False
                result.segments_completed = idx
                result.message = 'Job cancelled'
                goal_handle.canceled()
                self.get_logger().info('Job cancelled')
                return result

            # Handle pause
            while self._state == self.STATE_PAUSED:
                self._stop_paint()
                if goal_handle.is_cancel_requested:
                    break
                await self._async_sleep(0.1)

            if goal_handle.is_cancel_requested:
                self._state = self.STATE_IDLE
                result.success = False
                result.segments_completed = idx
                result.message = 'Job cancelled during pause'
                goal_handle.canceled()
                return result

            # Build Nav2 path from segment waypoints
            nav_path = self._segment_to_path(segment)

            # Send path to Nav2
            self.get_logger().info(
                f'Executing segment {idx + 1}/{len(self._segments)} '
                f'({len(segment.waypoints)} waypoints)'
            )

            nav2_goal = FollowPath.Goal()
            nav2_goal.path = nav_path

            send_goal_future = self._nav2_client.send_goal_async(nav2_goal)
            nav2_goal_handle = await send_goal_future

            if not nav2_goal_handle.accepted:
                self.get_logger().error(f'Nav2 rejected segment {idx}')
                self._state = self.STATE_ERROR
                result.success = False
                result.segments_completed = idx
                result.message = f'Nav2 rejected segment {idx}'
                goal_handle.abort()
                return result

            self._nav2_goal_handle = nav2_goal_handle

            # Start painting for this segment
            self._start_paint(segment)

            # Wait for segment completion
            nav2_result_future = nav2_goal_handle.get_result_async()
            nav2_result = await nav2_result_future

            # Stop painting at end of segment
            self._stop_paint()

            # Calculate segment distance
            seg_dist = self._compute_segment_distance(segment)
            self._total_distance += seg_dist

            # Publish feedback
            feedback = ExecutePaintJob.Feedback()
            feedback.current_segment = idx + 1
            feedback.total_segments = len(self._segments)
            feedback.progress_percent = ((idx + 1) / len(self._segments)) * 100.0
            feedback.current_speed = segment.speed
            goal_handle.publish_feedback(feedback)

        # Job complete
        self._state = self.STATE_COMPLETE
        result.success = True
        result.total_distance_m = self._total_distance
        result.paint_used_ml = 0.0  # Calculated by paint controller
        result.segments_completed = len(self._segments)
        result.message = 'Job completed successfully'
        goal_handle.succeed()

        self.get_logger().info(
            f'Job {self._current_job_id} complete: '
            f'{result.segments_completed} segments, {result.total_distance_m:.1f}m'
        )

        self._state = self.STATE_IDLE
        return result

    def _segment_to_path(self, segment: PaintSegment) -> Path:
        """Convert a PaintSegment to a Nav2 Path message."""
        path = Path()
        path.header.frame_id = 'map'
        path.header.stamp = self.get_clock().now().to_msg()

        for i, wp in enumerate(segment.waypoints):
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = wp.x
            pose.pose.position.y = wp.y
            pose.pose.position.z = 0.0

            # Compute orientation from direction to next waypoint
            if i < len(segment.waypoints) - 1:
                nxt = segment.waypoints[i + 1]
                yaw = math.atan2(nxt.y - wp.y, nxt.x - wp.x)
            elif i > 0:
                prev = segment.waypoints[i - 1]
                yaw = math.atan2(wp.y - prev.y, wp.x - prev.x)
            else:
                yaw = 0.0

            pose.pose.orientation.z = math.sin(yaw / 2.0)
            pose.pose.orientation.w = math.cos(yaw / 2.0)
            path.poses.append(pose)

        return path

    def _start_paint(self, segment: PaintSegment):
        """Command paint spray on."""
        cmd = PaintCommand()
        cmd.spray_on = True
        cmd.flow_rate = segment.speed  # Flow rate tied to speed
        self._paint_cmd_pub.publish(cmd)

    def _stop_paint(self):
        """Command paint spray off."""
        cmd = PaintCommand()
        cmd.spray_on = False
        cmd.flow_rate = 0.0
        self._paint_cmd_pub.publish(cmd)

    def _compute_segment_distance(self, segment: PaintSegment) -> float:
        """Sum euclidean distances between consecutive waypoints."""
        dist = 0.0
        for i in range(1, len(segment.waypoints)):
            dx = segment.waypoints[i].x - segment.waypoints[i - 1].x
            dy = segment.waypoints[i].y - segment.waypoints[i - 1].y
            dist += math.sqrt(dx * dx + dy * dy)
        return dist

    def _publish_status(self):
        """Publish current job status."""
        msg = JobStatus()
        msg.job_id = self._current_job_id
        msg.state = self._state
        msg.current_segment = self._current_segment_idx
        msg.total_segments = len(self._segments)
        if msg.total_segments > 0:
            msg.progress = float(self._current_segment_idx) / float(msg.total_segments)
        else:
            msg.progress = 0.0
        msg.status_message = self._state_name(self._state)
        self._status_pub.publish(msg)

    def _state_name(self, state: int) -> str:
        names = {
            self.STATE_IDLE: 'IDLE',
            self.STATE_RUNNING: 'RUNNING',
            self.STATE_PAUSED: 'PAUSED',
            self.STATE_COMPLETE: 'COMPLETE',
            self.STATE_ERROR: 'ERROR',
        }
        return names.get(state, 'UNKNOWN')

    # --- Service callbacks ---

    def _load_job_cb(self, request, response):
        """Load a job definition for later execution."""
        try:
            self._loaded_jobs[request.job_id] = request.job_data_json
            response.success = True
            response.message = f'Job {request.job_id} loaded'
            self.get_logger().info(f'Loaded job {request.job_id}')
        except Exception as e:
            response.success = False
            response.message = str(e)
        return response

    def _start_job_cb(self, request, response):
        """Start a previously loaded job (placeholder - actual execution via action)."""
        if self._state == self.STATE_RUNNING:
            response.success = False
            response.message = 'A job is already running'
        elif request.job_id not in self._loaded_jobs:
            response.success = False
            response.message = f'Job {request.job_id} not loaded'
        else:
            response.success = True
            response.message = f'Job {request.job_id} ready to execute via action'
            self.get_logger().info(f'Job {request.job_id} start requested')
        return response

    def _pause_job_cb(self, request, response):
        """Pause or resume the current job."""
        if request.resume:
            if self._state == self.STATE_PAUSED:
                self._state = self.STATE_RUNNING
                response.success = True
                response.message = 'Job resumed'
                self.get_logger().info('Job resumed')
            else:
                response.success = False
                response.message = 'Job is not paused'
        else:
            if self._state == self.STATE_RUNNING:
                self._state = self.STATE_PAUSED
                response.success = True
                response.message = 'Job paused'
                self.get_logger().info('Job paused')
            else:
                response.success = False
                response.message = 'Job is not running'
        return response

    async def _async_sleep(self, seconds: float):
        """Non-blocking sleep using ROS2 rate."""
        rate = self.create_rate(1.0 / seconds)
        rate.sleep()

    def destroy_node(self):
        self._stop_paint()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PathManagerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
