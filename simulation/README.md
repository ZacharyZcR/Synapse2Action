# Simulation

## Unitree G1 through the official SDK2 contract

The G1 path uses Unitree's real `unitree_sdk2_python` DDS types and Unitree's
`unitree_mujoco` bridge. Both dependencies are pinned in `unitree.lock.json`;
there is no local substitute for `LowCmd`, `LowState`, DDS, or CRC handling.
The Python adapter is intentionally restricted to the loopback interface so it
cannot be pointed at a physical robot by accident. The reproducible acceptance
run uses an isolated, per-run Docker network instead.

Run the complete headless dynamic acceptance path:

```bash
./simulation/run_unitree_headless.sh
```

The runner builds pinned images when needed, starts Unitree's official C++
SDK2/RL Lab velocity controller before the simulator, and connects it to the
official Python MuJoCo bridge over DDS. Physics remains paused until the first
real `rt/lowcmd` frame arrives. Acceptance requires 14 seconds without external
support, all 29 motors, a minimum and final base height of at least 0.65 m, an
upright quaternion, and controller logs proving `FSM: Start Velocity`. Reports
are written to `reports/simulation/` and are intentionally not committed.

On an Ubuntu machine with a working Python development toolchain, prepare the
official sources and Python dependencies:

```bash
./simulation/bootstrap_unitree.sh
```

Edit `simulation/vendor/unitree_mujoco/simulate_python/config.py` to use:

```python
ROBOT = "g1"
DOMAIN_ID = 1
INTERFACE = "lo"
USE_JOYSTICK = 0
```

Start Unitree's simulator in one terminal:

```bash
cd simulation/vendor/unitree_mujoco/simulate_python
python3 unitree_mujoco.py
```

Then run the SDK smoke path from the project root:

```bash
PYTHONPATH=src python3 simulation/g1_sdk_smoke.py
```

Acceptance requires a 29-motor `LowState`, advancing timestamps, and successful
publication of neutral `LowCmd` frames with SDK2 CRC on `rt/lowcmd`. Neutral
frames validate the communication boundary; they are not a standing or walking
controller. `unitree_mujoco` exposes low-level SDK2 compatibility only, so G1
balance, locomotion, and manipulation controllers remain separate milestones.

The next bounded step reproduces Unitree's official G1 29-DOF `FixStand`
profile: the current joint state is linearly interpolated over three seconds to
the official posture, using the official per-joint `kp` and `kd` arrays.

```bash
PYTHONPATH=src python3 simulation/g1_sdk_fixstand.py
```

The controller stops commanding torque if `LowState` is older than 100 ms or
absolute roll/pitch exceeds 0.7 rad. Passing this command proves a fixed standing
transition only. The headless acceptance runner above is the dynamic balance
test; locomotion with a non-zero velocity command remains a separate scenario.

## ROS 2 + Gazebo navigation simulation

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
