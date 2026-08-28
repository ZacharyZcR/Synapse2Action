from __future__ import annotations

import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "simulation" / "ros2_ws" / "src" / "synapse2action_sim"


class Ros2SimulationAssetTests(unittest.TestCase):
    def test_package_declares_runtime_dependencies(self) -> None:
        root = ET.parse(PACKAGE / "package.xml").getroot()
        dependencies = {node.text for node in root.findall("exec_depend")}
        self.assertTrue(
            {
                "geometry_msgs",
                "nav_msgs",
                "rclpy",
                "ros_gz_bridge",
                "ros_gz_sim",
                "rosgraph_msgs",
                "sensor_msgs",
                "visualization_msgs",
            }.issubset(dependencies)
        )

    def test_world_wires_robot_sensors_and_actuation(self) -> None:
        root = ET.parse(PACKAGE / "worlds" / "navigation.sdf").getroot()
        world = root.find("world")
        self.assertIsNotNone(world)
        plugins = {plugin.get("name"): plugin for plugin in world.findall("plugin")}
        self.assertIn("gz::sim::systems::Physics", plugins)
        self.assertIn("gz::sim::systems::Sensors", plugins)

        models = {model.get("name"): model for model in world.findall("model")}
        self.assertEqual(models["crate"].findtext("pose"), "1 0 0.25 0 0 0")
        self.assertEqual(models["goal"].findtext("pose"), "2 0 0.01 0 0 0")

        robot = models["synapse_bot"]
        joints = {joint.get("name") for joint in robot.findall("joint")}
        self.assertTrue({"left_wheel_joint", "right_wheel_joint", "camera_joint"}.issubset(joints))
        drive = robot.find("plugin[@name='gz::sim::systems::DiffDrive']")
        self.assertIsNotNone(drive)
        self.assertEqual(drive.findtext("topic"), "/model/synapse_bot/cmd_vel")
        self.assertEqual(drive.findtext("odom_topic"), "/model/synapse_bot/odometry")
        camera = robot.find("link[@name='camera_link']/sensor[@type='camera']")
        self.assertIsNotNone(camera)
        self.assertEqual(camera.findtext("topic"), "/camera/image_raw")

    def test_bridge_contract_has_all_navigation_topics(self) -> None:
        bridge = (PACKAGE / "config" / "bridge.yaml").read_text()
        expected = {
            "/clock": "GZ_TO_ROS",
            "/cmd_vel": "ROS_TO_GZ",
            "/odom": "GZ_TO_ROS",
            "/camera/image_raw": "GZ_TO_ROS",
        }
        for topic, direction in expected.items():
            block = bridge.split(f"ros_topic_name: {topic}", 1)[1].split("\n\n", 1)[0]
            self.assertIn(f"direction: {direction}", block)

    def test_python_assets_compile_and_launch_full_flow(self) -> None:
        launch = (PACKAGE / "launch" / "navigation.launch.py").read_text()
        obstacle = (PACKAGE / "synapse2action_sim" / "obstacle_publisher.py").read_text()
        ast.parse(launch)
        ast.parse(obstacle)
        self.assertIn("synapse2action.ros2_robot_server", launch)
        self.assertIn('"--vla-navigation-demo"', launch)
        self.assertIn('"/obstacles"', obstacle)

    def test_documented_one_command_acceptance(self) -> None:
        documentation = (ROOT / "simulation" / "README.md").read_text()
        self.assertIn("colcon build --symlink-install", documentation)
        self.assertIn("start_controller:=true", documentation)
        self.assertIn("simulation-report.json", documentation)


if __name__ == "__main__":
    unittest.main()
