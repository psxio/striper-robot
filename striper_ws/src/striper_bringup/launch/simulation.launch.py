"""Simulation launch file for the Striper parking lot line-painting robot.

Launches Gazebo with a parking lot world, spawns the robot, and starts
all localization, navigation, and application nodes with simulated sensors.
"""
import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    GroupAction,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Package paths
    bringup_pkg = FindPackageShare('striper_bringup')
    description_pkg = FindPackageShare('striper_description')

    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time')
    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    log_level = LaunchConfiguration('log_level')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation clock')

    declare_world = DeclareLaunchArgument(
        'world', default_value='parking_lot',
        description='Gazebo world name')

    declare_gui = DeclareLaunchArgument(
        'gui', default_value='true',
        description='Launch Gazebo GUI')

    declare_log_level = DeclareLaunchArgument(
        'log_level', default_value='info',
        description='Log level')

    # Config paths
    ekf_local_config = PathJoinSubstitution([bringup_pkg, 'config', 'ekf_local.yaml'])
    ekf_global_config = PathJoinSubstitution([bringup_pkg, 'config', 'ekf_global.yaml'])
    nav2_config = PathJoinSubstitution([bringup_pkg, 'config', 'nav2_params.yaml'])

    # URDF via xacro
    urdf_file = PathJoinSubstitution([description_pkg, 'urdf', 'striper.urdf.xacro'])
    robot_description = Command(['xacro ', urdf_file])

    # ==================== Gazebo ====================
    gazebo_server = ExecuteProcess(
        cmd=['gzserver', '--verbose',
             PathJoinSubstitution([bringup_pkg, 'worlds', world]),
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
    )

    gazebo_client = ExecuteProcess(
        condition=IfCondition(gui),
        cmd=['gzclient'],
        output='screen',
    )

    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'striper',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.2',
            '-Y', '0.0',
        ],
        output='screen',
    )

    # ==================== Robot State Publisher ====================
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Localization (EKF) ====================
    ekf_local_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_local_node',
        output='screen',
        parameters=[ekf_local_config, {'use_sim_time': use_sim_time}],
        remappings=[('odometry/filtered', 'odometry/local')],
        arguments=['--ros-args', '--log-level', log_level],
    )

    ekf_global_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_global_node',
        output='screen',
        parameters=[ekf_global_config, {'use_sim_time': use_sim_time}],
        remappings=[('odometry/filtered', 'odometry/global')],
        arguments=['--ros-args', '--log-level', log_level],
    )

    navsat_transform_node = Node(
        package='robot_localization',
        executable='navsat_transform_node',
        name='navsat_transform_node',
        output='screen',
        parameters=[ekf_global_config, {'use_sim_time': use_sim_time}],
        remappings=[
            ('imu/data', 'imu/data'),
            ('gps/fix', 'gps/fix'),
            ('odometry/filtered', 'odometry/global'),
            ('odometry/gps', 'odometry/gps'),
        ],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Nav2 ====================
    nav2_group = GroupAction(
        actions=[
            Node(
                package='nav2_controller',
                executable='controller_server',
                output='screen',
                parameters=[nav2_config, {'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='nav2_behaviors',
                executable='behavior_server',
                output='screen',
                parameters=[nav2_config, {'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='nav2_velocity_smoother',
                executable='velocity_smoother',
                output='screen',
                parameters=[nav2_config, {'use_sim_time': use_sim_time}],
                remappings=[
                    ('cmd_vel', 'cmd_vel_nav'),
                    ('cmd_vel_smoothed', 'cmd_vel'),
                ],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='nav2_lifecycle_manager',
                executable='lifecycle_manager',
                name='lifecycle_manager_navigation',
                output='screen',
                parameters=[nav2_config, {'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
        ],
    )

    # ==================== Simulated Sensors ====================
    fake_gps_node = Node(
        package='striper_simulation',
        executable='fake_gps_node',
        name='fake_gps_node',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'datum_latitude': 40.7580,
            'datum_longitude': -73.9855,
            'datum_altitude': 10.0,
            'publish_rate': 5.0,
            'noise_stddev': 0.5,
        }],
        arguments=['--ros-args', '--log-level', log_level],
    )

    paint_visualizer_node = Node(
        package='striper_simulation',
        executable='paint_visualizer_node',
        name='paint_visualizer_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Safety (relaxed for simulation) ====================
    safety_monitor_node = Node(
        package='striper_safety',
        executable='safety_monitor_node',
        name='safety_monitor_node',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'obstacle_stop_distance': 0.3,
            'obstacle_warning_distance': 1.0,
            'geofence_radius': 500.0,
        }],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Application Nodes ====================
    path_manager_node = Node(
        package='striper_navigation',
        executable='path_manager_node',
        name='path_manager_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    paint_controller_node = Node(
        package='striper_navigation',
        executable='paint_controller_node',
        name='paint_controller_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    return LaunchDescription([
        # Arguments
        declare_use_sim_time,
        declare_world,
        declare_gui,
        declare_log_level,
        # Gazebo
        gazebo_server,
        gazebo_client,
        # Robot description
        robot_state_publisher_node,
        spawn_robot,
        # Localization
        ekf_local_node,
        ekf_global_node,
        navsat_transform_node,
        # Navigation
        nav2_group,
        # Simulated sensors
        fake_gps_node,
        paint_visualizer_node,
        # Safety
        safety_monitor_node,
        # Application
        path_manager_node,
        paint_controller_node,
    ])
