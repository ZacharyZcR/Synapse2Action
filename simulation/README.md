# Simulation

## OpenPI policy research backend

OpenPI is pinned as a candidate policy backend and a reference for LeRobot data
transforms, normalization, action-chunk inference, and remote policy serving. It
does not replace the Harness, safety supervisor, whole-body controller, or
independent verifier. Fetch the exact source revision without installing Python
dependencies or model checkpoints:

```bash
./simulation/bootstrap_openpi.sh
```

The checkout is stored under ignored `simulation/vendor/openpi/`; the committed
record is `simulation/openpi.lock.json`. The published OpenPI checkpoints do not
provide a task-ready Unitree G1 action space, so G1 integration remains a future
adapter and fine-tuning task rather than a current capability.

## GR00T whole-body VLA status

The accepted local baseline uses the public GR00T N1.6 Unitree G1
apple-to-plate checkpoint, the matching official whole-body controller, and its
robosuite/MuJoCo environment. Synapse2Action launches that stack behind the
confirmation-gated Harness and independently records seeded grasp, lift,
transport, contact, release, stable-placement, and standing evidence. LeRobot
is the committed standard policy/dataset/robot dependency; the direct N1.6/WBC
process runner is a transitional humanoid adapter where the required upstream
boundary is not yet exposed through LeRobot.

Run one evidence-preserving Harness episode with:

```bash
PYTHONPATH=src python3 simulation/run_harness_unitree.py \
  --task pick-place --policy groot --planner mock --seed 1001
```

Run a reproducible multi-seed suite with:

```bash
PYTHONPATH=src python3 simulation/run_groot_seeded_benchmark.py \
  --seeds 1001 1002 1003
```

### Future GR00T N1.7 + SONIC experiment

The proposed future G1 control path replaces the task-specific C++ pick-and-place fixture
with NVIDIA's open-source Isaac-GR00T N1.7 and GEAR-SONIC whole-body controller.
The VLA emits a 78-dimensional action: a 64-dimensional SONIC motion token and
14 hand-joint targets. SONIC owns the 50 Hz whole-body rollout and balance layer;
it is a controller, not a hard-coded task trajectory.

Source commits and SONIC v1.1 ONNX checksums are pinned in
`groot_sonic.lock.json`. On Ubuntu, fetch the exact sources and approximately
200 MB of deployment weights with:

```bash
./simulation/bootstrap_groot_sonic.sh
```

Current status: both upstream repositories and the verified SONIC v1.1 ONNX
weights have been staged locally. Python entry points compile, and the official
G1 simulation/VLA interfaces have been inspected. The full GR00T PolicyServer
to SONIC to MuJoCo loop has **not** yet been accepted because the staging host
is Apple Silicon macOS while the upstream C++ deployment requires Ubuntu with
CUDA/TensorRT. Continue on the Ubuntu GPU host in this order:

1. build the upstream SONIC deployment and run its MuJoCo sim2sim quick start;
2. inject controlled 64-dimensional motion tokens and record measured joints;
3. run a `UNITREE_G1_SONIC` fine-tuned GR00T PolicyServer;
4. adapt the project's `TaskSpec` and stage telemetry to the official ZMQ path;
5. compare GR00T-on and GR00T-off rollouts before removing the SmolVLA baseline.

The public GR00T base checkpoint is not a task-ready G1 SONIC policy. A
`UNITREE_G1_SONIC` fine-tuned checkpoint is still required for manipulation.
Neither the upstream checkouts nor model binaries are committed to this
repository; `simulation/vendor/` remains an ignored, reproducible cache.

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

This single command executes `select -> plan -> review -> confirm -> policy -> Robot`
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
  --task pick-place --task-spec experiments/tasks/g1_pick_place.json \
  --output reports/simulation/harness-unitree-pick-place.json
```

## Real SmolVLA inference boundary

Check the independently installed GR00T N1.7 and GEAR-SONIC stack without
starting a model server or simulator:

```bash
python3 simulation/check_groot_n17_readiness.py
```

Add `--check-access` to distinguish a missing Hugging Face login from a gated
`nvidia/Cosmos-Reason2-2B` license that has not yet been granted. The JSON
report contains no token or credential material. Local readiness does not mean
the model fits GPU memory or completes a closed-loop rollout.

After gated access is granted, start the local N1.7 policy server with:

```bash
./simulation/run_groot_n17_server.sh
```

The launcher refuses to start when local files or gated access are missing and
uses `UNITREE_G1_SONIC`, port `5550`, and `cuda:0` by default. Override these
with `S2A_GROOT_N17_MODEL_DIR`, `S2A_GROOT_N17_PORT`, or
`S2A_GROOT_N17_DEVICE`. The matching SONIC policy client can be inspected or
run through the compatible N1.7 environment with:

```bash
./simulation/run_groot_n17_sonic_client.sh --help
```

This wrapper avoids the upstream inference installer mismatch where the
dependency is named `Isaac-GR00T` but the current package metadata is `gr00t`.

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
SO100 action space controls G1.

Record the physically verified SDK2/MuJoCo episode and convert its 29 joint
states, 29 `LowCmd` targets, three rendered cameras, and task text into an
official LeRobot Dataset v3 tree:

```bash
./simulation/run_lerobot_dataset.sh
```

Run the real SmolVLA training integration gate and then load the resulting
checkpoint for a 29-dimensional inference check:

```bash
S2A_TRAIN_STEPS=1 ./simulation/run_smolvla_g1_train.sh
```

The one-step default proves dataset loading, feature inference, forward and
backward passes, local checkpoint saving, and checkpoint inference without
publishing to the Hub. It is not a task-quality claim. A useful manipulation
policy requires varied training episodes and held-out closed-loop evaluation.
The converter accepts one or more recorded `.npz` episodes before the output
path, so scene variations can remain separate LeRobot episodes instead of being
concatenated into one leaking trajectory. Evaluate a trained checkpoint against
a recorded episode with:

```bash
docker run --rm \
  --volume "$PWD:/workspace/current:ro" \
  --volume "$PWD/reports:/workspace/reports" \
  synapse2action-smolvla:0.6.1 \
  python simulation/evaluate_smolvla_g1_offline.py \
  /workspace/reports/training/smolvla-g1/checkpoints/last/pretrained_model \
  /workspace/reports/simulation/g1-pick-place-episode.npz \
  --report /workspace/reports/training/smolvla-g1-offline.json
```

The report separates full 29-DOF error from the waist and shoulder/elbow joints
that manipulation controls. Passing checkpoint-shape validation alone is not a
closed-loop task-quality result.

Generate the five-episode manipulation suite with independently timed SDK2
trajectories using:

```bash
./simulation/run_lerobot_dataset_suite.sh
```

Every trajectory must independently pass the MuJoCo grasp, lift, transport,
rectangular tray, and unsupported-standing checks before conversion. The suite
contains 700 frames across five LeRobot episodes; it is intended for an
episode-level train/evaluation split, not a random frame split.

Train for one full pass over the 560 frames in the first four episodes with the
final 140-frame episode held out, then reload the checkpoint and report its
held-out manipulation-joint error:

```bash
./simulation/run_smolvla_g1_suite_train.sh
```

## Public offline SSVEP gate

Run a subject-independent benchmark on the open PhysioNet MAMEM SSVEP
Experiment 3 recordings:

```bash
./simulation/run_public_ssvep.sh
```

The locked container uses the official WFDB SDK to download and read 14-channel
Emotiv EPOC recordings. Subjects 001-002 are training data, subject 003 is used
only for confidence calibration, and subject 004 is held out for testing. The
benchmark compares multi-harmonic CCA with a PyTorch spectral MLP, applies an
explicit abstention threshold and signal-quality gate, and replays accepted
select, confirm, cancel, and stop predictions through the same `Harness` intent
interface. Generated recordings and reports remain ignored local artifacts.

Run the accepted public EEG selection and confirmation through the Harness and
into the physically verified SDK2/MuJoCo G1 pick-and-place simulation:

```bash
./simulation/run_public_ssvep_unitree.sh
```

The runner refuses an unaccepted EEG benchmark or a decoded sequence other
than select followed by confirm. The simulated robot still uses the independent
physical object, lift, drop-zone, and standing acceptance checks.

## Hardware-free live EEG stream

Run a real BrainFlow and Lab Streaming Layer acquisition/synchronization path
without an EEG headset:

```bash
./simulation/run_live_eeg_unitree.sh
```

The pinned x86-64 container runs BrainFlow 5.19.0's Synthetic Board and official
liblsl/pylsl streams under Docker emulation on ARM hosts. Separate EEG and
marker outlets are resolved by inlets, all samples retain monotonic LSL
timestamps, and select and confirm occupy distinct windows. A same-session
signal/noise calibration derives the confidence threshold; sample completeness,
flat-channel checks, amplitude drift, latency, abstention, and false activation
are reported. Accepted selection and confirmation then enter the unchanged
Harness and SDK2/MuJoCo G1 task. This validates the software boundary only;
human workload and physical electrode impedance remain hardware-study metrics.

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
