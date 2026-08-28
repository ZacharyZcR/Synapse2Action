from __future__ import annotations

import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    package_share = get_package_share_directory("synapse2action_sim")
    ros_gz_share = get_package_share_directory("ros_gz_sim")
    world = os.path.join(package_share, "worlds", "navigation.sdf")
    bridge = os.path.join(package_share, "config", "bridge.yaml")

    http_port = LaunchConfiguration("http_port")
    report_path = LaunchConfiguration("report_path")
    start_http_bridge = LaunchConfiguration("start_http_bridge")
    start_controller = LaunchConfiguration("start_controller")

    return LaunchDescription(
        [
            DeclareLaunchArgument("http_port", default_value="8765"),
            DeclareLaunchArgument("report_path", default_value="simulation-report.json"),
            DeclareLaunchArgument("start_http_bridge", default_value="true"),
            DeclareLaunchArgument("start_controller", default_value="false"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(ros_gz_share, "launch", "gz_sim.launch.py")),
                launch_arguments={"gz_args": ["-r -v 3 ", world]}.items(),
            ),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="synapse2action_bridge",
                parameters=[{"config_file": bridge, "use_sim_time": True}],
                output="screen",
            ),
            Node(
                package="synapse2action_sim",
                executable="obstacle_publisher",
                parameters=[{"use_sim_time": True}],
                output="screen",
            ),
            ExecuteProcess(
                cmd=[
                    sys.executable,
                    "-m",
                    "synapse2action.ros2_robot_server",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    http_port,
                ],
                condition=IfCondition(start_http_bridge),
                output="screen",
            ),
            TimerAction(
                period=5.0,
                actions=[
                    ExecuteProcess(
                        cmd=[
                            sys.executable,
                            "-m",
                            "synapse2action",
                            "--vla-navigation-demo",
                            "--robot-transport",
                            "http",
                            "--robot-base-url",
                            ["http://127.0.0.1:", http_port, "/v1"],
                            "--output",
                            report_path,
                        ],
                        condition=IfCondition(start_controller),
                        output="screen",
                    )
                ],
            ),
        ]
    )
