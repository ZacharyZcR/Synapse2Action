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

Run the A-to-B locomotion scenario with a bounded 0.3 m/s forward command:

```bash
./simulation/run_unitree_headless.sh locomotion 0.8 0.2 0.3
```

Run the same physical scenario through the complete confirmation-gated Harness:

```bash
PYTHONPATH=src python3 simulation/run_harness_unitree.py \
  --destination point_b --target-x 0.8 --target-y 0.0 --target-yaw 0.0 \
  --output reports/simulation/harness-unitree.json
```

This single command executes `select -> confirm -> plan -> policy -> Robot`
before starting the official SDK2 controller and MuJoCo bridge. The Harness only
completes after the independent simulator acceptance and measured final pose
checks pass.

MuJoCo publishes the measured base pose on SDK2's standard
`rt/sportmodestate` topic. The C++ controller computes velocity from the live
target error into the robot frame and produces `vx`, `vy`, and `yaw_rate`. It
slows inside the approach region and commands zero within 5 cm. In addition to
balance checks, acceptance requires position error within 10 cm, yaw error
within 0.15 rad, and low final translational/angular velocity.

Run the collision-obstacle and waypoint replanning scenario:

```bash
./simulation/run_unitree_headless.sh obstacle 0.9 0.0 0.0
```

The runner adds a real MuJoCo collision box on the direct path. The controller
creates two detour waypoints from the measured pose, resumes the final goal
after reaching them, and records both waypoint events. Acceptance requires
physical clearance from the box, visible lateral deviation, final goal
convergence, and a stopped upright robot.

Run the dynamic-obstacle scenario:

```bash
./simulation/run_unitree_headless.sh dynamic-obstacle 0.9 0.0 0.0
```

The collision box enters the route after motion starts. Its SDK2 range reading
triggers the controller's online detour; no obstacle position is supplied to
the controller beforehand.

Run the scripted G1 pick-and-place acceptance:

```bash
./simulation/run_unitree_pick_place.sh
```

The official velocity policy continues to balance the lower body while a
bounded trajectory overrides the waist and arm joint targets. The 29-DOF model
has rubber hands rather than actuated fingers, so the scene activates a MuJoCo
weld only after both wrists reach the object. Acceptance requires a physical
grasp, at least 10 cm of measured lift, transport, release into the collision
tray, and an unsupported standing G1. Object position is never teleported.

Run the same task through selection and confirmation in the Harness:

```bash
PYTHONPATH=src python3 simulation/run_harness_unitree.py \
  --task pick-place --destination red_cube \
  --output reports/simulation/harness-unitree-pick-place.json
```

## Real SmolVLA inference boundary

Run the official 450M `lerobot/smolvla_base` checkpoint on three synthetic
camera views, six-dimensional state, and two different language instructions:

```bash
./simulation/run_smolvla_smoke.sh
```

The runner builds the pinned LeRobot 0.6.1 CPU image, uses the official
preprocessor and `SmolVLAPolicy.select_action`, and requires finite six-axis
actions that change with the instruction. The first run downloads weights into
the ignored `simulation/vendor/huggingface` cache. This proves real checkpoint
loading and language-conditioned inference; it does not claim that the base
SO100 action space controls G1. G1 dataset conversion and task-specific
fine-tuning remain the next gate.

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
