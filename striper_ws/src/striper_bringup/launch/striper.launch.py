"""Main hardware launch file for the Striper parking lot line-painting robot.

Launches all hardware drivers, localization, navigation, and application nodes.
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Package paths
    bringup_pkg = FindPackageShare('striper_bringup')
    description_pkg = FindPackageShare('striper_description')

    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_nav2 = LaunchConfiguration('enable_nav2')
    enable_safety = LaunchConfiguration('enable_safety')
    log_level = LaunchConfiguration('log_level')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock')

    declare_enable_nav2 = DeclareLaunchArgument(
        'enable_nav2', default_value='true',
        description='Enable Nav2 navigation stack')

    declare_enable_safety = DeclareLaunchArgument(
        'enable_safety', default_value='true',
        description='Enable safety monitoring nodes')

    declare_log_level = DeclareLaunchArgument(
        'log_level', default_value='info',
        description='Log level (debug, info, warn, error, fatal)')

    # Config file paths
    ekf_local_config = PathJoinSubstitution([bringup_pkg, 'config', 'ekf_local.yaml'])
    ekf_global_config = PathJoinSubstitution([bringup_pkg, 'config', 'ekf_global.yaml'])
    nav2_config = PathJoinSubstitution([bringup_pkg, 'config', 'nav2_params.yaml'])

    # URDF via xacro
    urdf_file = PathJoinSubstitution([description_pkg, 'urdf', 'striper.urdf.xacro'])
    robot_description = Command(['xacro ', urdf_file])

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
        condition=IfCondition(enable_nav2),
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

    # ==================== Hardware Drivers ====================
    motor_driver_node = Node(
        package='striper_hardware',
        executable='motor_driver',
        name='motor_driver',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    imu_driver_node = Node(
        package='striper_hardware',
        executable='imu_node',
        name='imu_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    gps_driver_node = Node(
        package='striper_hardware',
        executable='gps_node',
        name='gps_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    paint_valve_node = Node(
        package='striper_hardware',
        executable='paint_valve',
        name='paint_valve',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Safety ====================
    safety_group = GroupAction(
        condition=IfCondition(enable_safety),
        actions=[
            Node(
                package='striper_safety',
                executable='safety_supervisor',
                name='safety_supervisor',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='striper_safety',
                executable='obstacle_detector',
                name='obstacle_detector',
                output='screen',
                parameters=[{
                    'use_sim_time': use_sim_time,
                    'stop_distance': 0.5,
                    'warning_distance': 1.5,
                }],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='striper_safety',
                executable='geofence',
                name='geofence',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='striper_safety',
                executable='watchdog',
                name='watchdog',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
            Node(
                package='striper_safety',
                executable='operator_override',
                name='operator_override',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time}],
                arguments=['--ros-args', '--log-level', log_level],
            ),
        ],
    )

    # ==================== Localization (Custom) ====================
    odom_publisher_node = Node(
        package='striper_localization',
        executable='odom_publisher',
        name='odom_publisher',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    datum_setter_node = Node(
        package='striper_localization',
        executable='datum_setter',
        name='datum_setter',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    # ==================== Application Nodes ====================
    path_manager_node = Node(
        package='striper_navigation',
        executable='path_manager',
        name='path_manager',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    speed_regulator_node = Node(
        package='striper_navigation',
        executable='speed_regulator',
        name='speed_regulator',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    paint_controller_node = Node(
        package='striper_navigation',
        executable='paint_controller',
        name='paint_controller',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        arguments=['--ros-args', '--log-level', log_level],
    )

    return LaunchDescription([
        # Arguments
        declare_use_sim_time,
        declare_enable_nav2,
        declare_enable_safety,
        declare_log_level,
        # Robot description
        robot_state_publisher_node,
        # Localization
        ekf_local_node,
        ekf_global_node,
        navsat_transform_node,
        # Navigation
        nav2_group,
        # Hardware
        motor_driver_node,
        imu_driver_node,
        gps_driver_node,
        paint_valve_node,
        # Safety
        safety_group,
        # Localization (Custom)
        odom_publisher_node,
        datum_setter_node,
        # Application
        path_manager_node,
        speed_regulator_node,
        paint_controller_node,
    ])
