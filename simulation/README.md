# ROS 2 + Gazebo navigation simulation

This package runs the existing Synapse2Action navigation flow against a simulated differential-drive robot. It targets Ubuntu 24.04, ROS 2 Jazzy, and Gazebo Harmonic. No physical device is required.

The world contains a robot at point A `(0, 0)`, a crate obstacle at `(1, 0)`, and point B at `(2, 0)`. Gazebo publishes camera and odometry data; `ros_gz_bridge` maps those topics to ROS 2; the existing ROS runtime exposes them through the HTTP robot protocol. Commands travel back through `/cmd_vel` to Gazebo's differential-drive system.

## Prerequisites

Install ROS 2 Jazzy, Gazebo Harmonic, `ros-jazzy-ros-gz`, `python3-colcon-common-extensions`, and the standard ROS message packages listed in `package.xml`.

## Build and run

```bash
cd simulation/ros2_ws
python3 -m pip install -e ../..
colcon build --symlink-install
source install/setup.bash
ros2 launch synapse2action_sim navigation.launch.py
```

The default launch starts Gazebo, the topic bridge, obstacle publisher, and HTTP robot runtime. Start the full A-to-B controller in the same launch:

```bash
ros2 launch synapse2action_sim navigation.launch.py start_controller:=true
```

The controller writes `simulation-report.json` when it finishes. A successful run must report a terminal navigation state and leave the robot stopped. To run the controller manually instead:

```bash
PYTHONPATH=src python3 -m synapse2action \
  --vla-navigation-demo \
  --robot-transport http \
  --robot-base-url http://127.0.0.1:8765/v1 \
  --output simulation-report.json
```

## Inspect the live data path

```bash
ros2 topic hz /odom
ros2 topic hz /camera/image_raw
ros2 topic echo /cmd_vel --once
curl http://127.0.0.1:8765/v1/observation
```

The current macOS development host does not contain ROS 2 or Gazebo, so repository tests validate package structure, topic contracts, SDF wiring, and Python syntax only. A Gazebo-capable ROS host is required to claim dynamic simulation acceptance.
