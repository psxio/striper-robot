# Striper Robot - Topic, Service, and Action Map

System wiring diagram for all ROS2 nodes.

---

## Topics

### Sensor Data

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `gps/fix` | `sensor_msgs/NavSatFix` | `gps_node`, `fake_gps` | `datum_setter`, `geofence`, `navsat_transform_node` |
| `gps/hdop` | `std_msgs/Float32` | `gps_node` | -- |
| `gps/fix_quality` | `std_msgs/String` | `gps_node` | -- |
| `imu/data` | `sensor_msgs/Imu` | `imu_node` | `navsat_transform_node` |
| `encoder_ticks` | `std_msgs/Int32MultiArray` | `motor_driver` | `odom_publisher` |
| `wheel_odom` | `nav_msgs/Odometry` | `odom_publisher` | EKF (via config) |
| `ultrasonic/front_left` | `sensor_msgs/Range` | `obstacle_detector` | -- |
| `ultrasonic/front_right` | `sensor_msgs/Range` | `obstacle_detector` | -- |

### Odometry and Localization

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `odom` | `nav_msgs/Odometry` | EKF (default output) | `speed_regulator`, `paint_controller`, `paint_visualizer` |
| `odometry/local` | `nav_msgs/Odometry` | `ekf_local_node` | -- |
| `odometry/global` | `nav_msgs/Odometry` | `ekf_global_node` | `navsat_transform_node` |
| `odometry/gps` | `nav_msgs/Odometry` | `navsat_transform_node` | EKF (via config) |
| `datum` | `geographic_msgs/GeoPoint` | `datum_setter` | `fake_gps` |

### Navigation and Motion

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `cmd_vel` | `geometry_msgs/Twist` | Nav2 velocity_smoother | `motor_driver` |
| `cmd_vel_nav` | `geometry_msgs/Twist` | Nav2 controller_server (remapped) | `safety_supervisor` |
| `cmd_vel_manual` | `geometry_msgs/Twist` | `operator_override` | -- |
| `speed_override_cmd_vel` | `geometry_msgs/Twist` | `speed_regulator` | -- |
| `paint_speed_setpoint` | `std_msgs/Float64` | (external) | `speed_regulator` |

### Paint System

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `paint_command` | `striper_msgs/PaintCommand` | `path_manager`, `paint_controller` | `paint_valve`, `paint_visualizer` |
| `paint_valve_state` | `std_msgs/Bool` | `paint_valve` | -- |
| `current_paint_segment` | `striper_msgs/PaintSegment` | (external) | `paint_controller`, `paint_visualizer` |

### Job Management

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `job_status` | `striper_msgs/JobStatus` | `path_manager` | -- |

### Safety System

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `safety_status` | `striper_msgs/SafetyStatus` | `safety_supervisor` | -- |
| `safety/obstacle_detected` | `std_msgs/Bool` | `obstacle_detector` | `safety_supervisor` |
| `safety/obstacle_distance` | `std_msgs/Float32` | `obstacle_detector` | -- |
| `safety/geofence_violation` | `std_msgs/Bool` | `geofence` | `safety_supervisor` |
| `safety/watchdog_timeout` | `std_msgs/Bool` | `watchdog` | `safety_supervisor` |
| `safety/cmd_vel_override` | `geometry_msgs/Twist` | `safety_supervisor` | -- |

### Operator Interface

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `joy` | `sensor_msgs/Joy` | joy_node (external) | `operator_override` |
| `operator/mode` | `std_msgs/String` | `operator_override` | -- |
| `operator/override_active` | `std_msgs/String` | `operator_override` | -- |

### Watchdog Heartbeats

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `/heartbeat/motor_driver` | `std_msgs/Bool` | `motor_driver` (expected) | `watchdog` |
| `/heartbeat/gps_node` | `std_msgs/Bool` | `gps_node` (expected) | `watchdog` |
| `/heartbeat/imu_node` | `std_msgs/Bool` | `imu_node` (expected) | `watchdog` |
| `/heartbeat/safety_supervisor` | `std_msgs/Bool` | `safety_supervisor` (expected) | `watchdog` |

### Status and Diagnostics

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `geofence/status` | `std_msgs/String` | `geofence` | -- |
| `watchdog/status` | `std_msgs/String` | `watchdog` | -- |
| `rtcm_corrections` | `std_msgs/String` | (external NTRIP client) | `gps_node` |

### Simulation

| Topic | Type | Publisher(s) | Subscriber(s) |
|-------|------|-------------|---------------|
| `sim/robot_pose` | `geometry_msgs/PoseStamped` | Gazebo (external) | `fake_gps` |
| `paint_trail` | `visualization_msgs/MarkerArray` | `paint_visualizer` | RViz (external) |

---

## Services

| Service | Type | Server Node | Client(s) |
|---------|------|------------|-----------|
| `load_job` | `striper_msgs/srv/LoadJob` | `path_manager` | (external / UI) |
| `start_job` | `striper_msgs/srv/StartJob` | `path_manager` | (external / UI) |
| `pause_job` | `striper_msgs/srv/PauseJob` | `path_manager` | (external / UI) |
| `set_datum` | `striper_msgs/srv/SetDatum` | `datum_setter` | (external / UI) |

---

## Actions

| Action | Type | Server Node | Client(s) |
|--------|------|------------|-----------|
| `execute_paint_job` | `striper_msgs/action/ExecutePaintJob` | `path_manager` | (external / UI) |
| `follow_path` | `nav2_msgs/action/FollowPath` | Nav2 controller_server | `path_manager` |

---

## TF Frames

| Parent | Child | Publisher |
|--------|-------|----------|
| `odom` | `base_link` | `odom_publisher` (wheel odom), EKF |
| `map` | `odom` | EKF (global), `navsat_transform_node` |

---

## Node Summary

| Package | Executable (setup.py) | Node Name | Description |
|---------|----------------------|-----------|-------------|
| `striper_navigation` | `path_manager` | `path_manager` | Job orchestrator, sequences paint segments via Nav2 |
| `striper_navigation` | `speed_regulator` | `speed_regulator` | PID speed controller for consistent paint application |
| `striper_navigation` | `paint_controller` | `paint_controller` | Spray on/off synchronization with position along segment |
| `striper_localization` | `odom_publisher` | `odom_publisher` | Differential drive wheel odometry from encoder ticks |
| `striper_localization` | `datum_setter` | `datum_setter` | GPS datum management and persistence |
| `striper_hardware` | `motor_driver` | `motor_driver` | ESP32 serial motor controller interface |
| `striper_hardware` | `imu_node` | `imu_node` | BNO085 IMU driver via I2C |
| `striper_hardware` | `gps_node` | `gps_node` | ZED-F9P GPS driver via serial NMEA |
| `striper_hardware` | `paint_valve` | `paint_valve` | GPIO solenoid valve control with safety timeout |
| `striper_safety` | `safety_supervisor` | `safety_supervisor` | Central safety arbiter: SAFE/WARNING/CRITICAL/ESTOP |
| `striper_safety` | `obstacle_detector` | `obstacle_detector` | HC-SR04 ultrasonic obstacle detection with filtering |
| `striper_safety` | `geofence` | `geofence` | GPS polygon boundary enforcement |
| `striper_safety` | `watchdog` | `watchdog` | Heartbeat monitor for critical nodes |
| `striper_safety` | `operator_override` | `operator_override` | Gamepad manual control with deadman switch |
| `striper_simulation` | `fake_gps` | `fake_gps` | Simulated GPS from Gazebo pose with noise |
| `striper_simulation` | `paint_visualizer` | `paint_visualizer` | RViz paint trail visualization |
