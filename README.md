# Synapse2Action / 念动

> From neural intent to safe robotic action.
> 从神经意图到安全、可验证的机器人动作。

Synapse2Action is an open-source research framework for integrating EEG-based brain-computer interfaces, Vision-Language-Action models, and robot control. It treats EEG as a sparse, high-level intent channel while delegating perception, planning, and motion execution to AI and robotics components.

Synapse2Action（念动）是一个集成 EEG 脑机接口、视觉-语言-动作模型（VLA）与机器人控制的开源研究框架。项目将 EEG 视为稀疏的高层意图通道，把环境感知、任务规划与运动执行交给 AI 和机器人系统完成。

## Vision / 项目愿景

The goal is not to continuously drive every robot joint with noisy EEG signals. The goal is to build a practical shared-autonomy system in which a person can select, confirm, cancel, or stop an action while the robot completes the physical task safely.

项目不追求用噪声较高的 EEG 连续控制每个机器人关节，而是构建实用的共享自主系统：用户负责选择、确认、取消或停止，机器人在安全约束下完成具体物理任务。

```text
EEG or simulated intent / EEG 或模拟意图
                ↓
Acquisition and synchronization / 采集与同步
                ↓
Intent decoding / 意图解码
                ↓
Task orchestration and safety / 任务编排与安全控制
                ↓
VLA policy or robot skill / VLA 策略或机器人技能
                ↓
Simulation or physical robot / 仿真或实体机器人
```

## Design Principles / 设计原则

- **Intent, not joints / 控制意图而非关节** — EEG provides a small set of robust commands instead of continuous motor trajectories.
- **Simulation first / 仿真优先** — every workflow must run without EEG hardware or a physical robot before real-device integration.
- **Shared autonomy / 共享自主** — AI handles perception and manipulation; the user retains meaningful control over goals and execution.
- **Safety by construction / 安全内建** — deterministic limits, collision checks, timeouts, and emergency stops remain outside generative models.
- **Replaceable components / 组件可替换** — acquisition devices, decoders, VLA models, simulators, and robots communicate through stable interfaces.
- **Reproducible evaluation / 可复现实验** — latency, decoding quality, task success, false activation, and user workload must be measured separately.

## Planned Architecture / 规划架构

| Layer / 层级 | Responsibility / 职责 | Candidate integrations / 候选集成 |
|---|---|---|
| Neural interface / 神经接口 | EEG acquisition, markers, synchronization / EEG 采集、事件标记、时间同步 | BrainFlow, LSL, OpenBCI |
| Neural decoding / 神经解码 | Signal quality, preprocessing, intent classification / 信号质量、预处理、意图分类 | MNE, pyRiemann, Braindecode |
| Orchestration / 任务编排 | State machine, confirmation, recovery / 状态机、确认与失败恢复 | Python, ROS 2 |
| Embodied policy / 具身策略 | Language- and vision-conditioned actions / 语言与视觉条件动作 | LeRobot, SmolVLA, OpenVLA |
| Robot control / 机器人控制 | Kinematics, collision checks, execution / 运动学、碰撞检查与执行 | ROS 2, MoveIt 2 |
| Environments / 运行环境 | Hardware-free validation and real deployment / 无硬件验证与真机部署 | MuJoCo, ManiSkill, physical robots |

The listed technologies are candidates, not committed dependencies. Each integration will be accepted only when it supports the smallest reproducible experiment for its milestone.

以上技术均为候选项，而不是已经确定的依赖。只有能够支撑对应里程碑最小可复现实验的组件，才会正式纳入项目。

## Roadmap / 路线图

The project follows a hardware-free-first strategy. Every external component begins with a deterministic substitute and is replaced one layer at a time: simulated intent before EEG, a fake robot before Unitree G1, a scripted policy before VLA, and a mock planner before a production LLM.

项目采用“无设备优先”策略。所有外部组件首先使用确定性替身，并且每次只替换一层：先模拟意图再接 EEG，先 Fake Robot 再接宇树 G1，先固定策略再接 VLA，先 Mock Planner 再接生产级大模型。

### Phase 0 — Contracts and Safety Kernel / 阶段 0：契约与安全内核

- [x] Adopt Python 3.12 as the primary implementation language. / 确定 Python 3.12 为主要实现语言。
- [ ] Define versioned schemas for intent, world state, plan, skill, action, and result. / 定义意图、世界状态、计划、技能、动作与结果的版本化 Schema。
- [ ] Define replaceable interfaces for `IntentSource`, `Planner`, `Policy`, `Robot`, and `Verifier`. / 为五类核心组件定义可替换接口。
- [x] Implement the explicit task states: idle, target selected, awaiting confirmation, armed, executing, verifying, completed, failed, cancelled, and emergency stopped. / 实现完整的显式任务状态机。
- [x] Specify invariants: no execution without confirmation, stop preempts every state, invalid model output never reaches a robot, and uncertainty defaults to no action. / 定义未确认不得执行、停止可抢占任意状态、非法模型输出不得到达机器人、不确定时默认不动作等不变量。
- [x] Define structured trace records and replay semantics. / 定义结构化执行轨迹与重放语义。

**Exit criterion / 完成标准:** the contracts, state transitions, and safety properties are testable without models, simulators, EEG devices, or robots. / 无需模型、仿真器、EEG 设备或机器人，即可测试全部契约、状态迁移和安全性质。

### Phase 1 — Deterministic Hardware-Free Core / 阶段 1：确定性无设备核心

- [ ] Implement scripted and keyboard intent sources for select, confirm, cancel, and stop. / 实现选择、确认、取消和停止的脚本与键盘意图源。
- [x] Implement `MockPlanner`, `ScriptedPolicy`, `FakeRobot`, and `RuleBasedVerifier`. / 实现四个确定性替身组件。
- [x] Build a typed skill registry with argument validation, preconditions, timeouts, and success conditions. / 建立包含参数校验、前置条件、超时和成功条件的类型化技能注册表。
- [x] Add scenario files for success, rejection, cancellation, timeout, malformed plans, and emergency stop. / 为成功、拒绝、取消、超时、非法计划和急停建立场景文件。
- [ ] Add property-based tests for illegal state transitions and adversarial inputs. / 为非法状态迁移和对抗输入加入性质测试。
- [x] Provide one-command scenario execution and deterministic replay. / 提供单命令场景执行与确定性重放。

**Exit criterion / 完成标准:** all safety tests pass on CPU, and the same scenario produces the same trace on every run. / 全部安全测试可在 CPU 上通过，同一场景每次生成一致轨迹。

### Phase 2 — LLM Planning Behind the Harness / 阶段 2：Harness 约束下的大模型规划

- [x] Define one OpenAI-compatible planner adapter instead of model-specific business logic. / 定义统一的 OpenAI-compatible Planner Adapter，避免在业务逻辑中绑定模型。
- [ ] Integrate DeepSeek-V4-Flash-0731 as the initial cloud planner. / 首先接入 DeepSeek-V4-Flash-0731 云端规划器。
- [ ] Integrate Qwen3.8-27B as the local planner option. / 接入 Qwen3.8-27B 本地规划器。
- [ ] Add GLM-5.3-Flash as an optional multimodal planner and verifier. / 将 GLM-5.3-Flash 作为可选多模态规划器与验证器。
- [x] Reject unknown skills, invalid arguments, stale object references, and plans that bypass confirmation. / 拒绝未知技能、非法参数、过期目标引用及绕过确认的计划。
- [ ] Benchmark schema compliance, invented-skill rate, dangerous-action refusal, latency, and recovery after provider failure. / 评测 Schema 遵循、虚构技能、危险动作拒绝、延迟与服务故障恢复。

**Exit criterion / 完成标准:** a real LLM can replace `MockPlanner` without changing the Harness, and no malformed plan can reach the policy or robot layers. / 真实 LLM 可在不修改 Harness 的情况下替换 MockPlanner，任何非法计划均无法进入策略或机器人层。

### Phase 3 — Unitree G1 Simulation / 阶段 3：宇树 G1 仿真

- [ ] Implement a stable `Robot` adapter for Unitree G1 observations and bounded actions. / 为宇树 G1 的观测与受限动作实现稳定 Robot Adapter。
- [ ] Integrate the LeRobot Unitree G1 MuJoCo environment for task-level simulation. / 接入 LeRobot 的 Unitree G1 MuJoCo 环境进行任务级仿真。
- [ ] Use `unitree_mujoco` separately to verify SDK2 messages and low-level controller compatibility. / 单独使用 unitree_mujoco 验证 SDK2 消息和低层控制器兼容性。
- [ ] Normalize joint naming, units, coordinate frames, timestamps, and action limits at the adapter boundary. / 在 Adapter 边界统一关节命名、单位、坐标系、时间戳与动作范围。
- [ ] Add watchdog, stale-state detection, action clipping, timeout, and safe-stop behavior. / 加入看门狗、状态过期检测、动作裁剪、超时与安全停止。
- [ ] Complete a scripted pick-and-place task in simulation. / 在仿真中完成固定策略抓取放置。

**Exit criterion / 完成标准:** the Harness controls a simulated G1 through the same high-level interface reserved for the physical robot, while low-level safety remains outside the LLM. / Harness 通过为真机预留的同一高层接口控制仿真 G1，低层安全完全独立于 LLM。

### Phase 4 — VLA Policy Integration / 阶段 4：VLA 策略集成

- [ ] Define a common `Policy` adapter for scripted skills, ACT, SmolVLA, and future VLA models. / 为固定技能、ACT、SmolVLA 与后续 VLA 定义统一 Policy Adapter。
- [x] Establish ACT or another deterministic imitation-learning baseline before VLA. / 在 VLA 前建立 ACT 或其他可控模仿学习基线。
- [ ] Integrate LeRobot data, training, inference, and checkpoint metadata. / 集成 LeRobot 数据、训练、推理与检查点元数据。
- [ ] Integrate SmolVLA as the first language-conditioned action policy. / 以 SmolVLA 作为首个语言条件动作策略。
- [ ] Validate action chunks against workspace, joint, velocity, acceleration, and duration limits. / 对动作块执行空间、关节、速度、加速度与持续时间校验。
- [ ] Verify task outcomes using robot state and visual evidence instead of model self-reporting. / 使用机器人状态与视觉证据验证结果，而非相信模型自报成功。
- [ ] Add bounded retry and deterministic recovery paths. / 加入有界重试与确定性恢复路径。

**Exit criterion / 完成标准:** the planner selects a registered skill and the VLA completes a simulated G1 manipulation task under Harness supervision. / Planner 选择已注册技能，VLA 在 Harness 监督下完成 G1 仿真操作任务。

### Phase 5 — Offline EEG Intent Decoding / 阶段 5：离线 EEG 意图解码

- [ ] Start with SSVEP and four discrete intents: select, confirm, cancel, and stop. / 以 SSVEP 和选择、确认、取消、停止四种离散意图起步。
- [ ] Add public-dataset playback before acquiring any hardware. / 在采购硬件前接入公开数据集回放。
- [ ] Build preprocessing, event alignment, signal-quality checks, and leakage-free evaluation. / 建立预处理、事件对齐、信号质量检查与无数据泄漏评测。
- [ ] Compare a classical decoder with a deep-learning baseline. / 比较传统解码器与深度学习基线。
- [ ] Calibrate confidence and implement explicit abstention for uncertain predictions. / 校准置信度，并对不确定预测明确拒识。
- [ ] Replay decoded intents through the exact Phase 1 Harness interface. / 通过阶段 1 的同一 Harness 接口重放解码意图。

**Exit criterion / 完成标准:** public EEG data can drive the simulated G1 pipeline, and low-quality or uncertain windows result in no action. / 公开 EEG 数据可驱动 G1 仿真管线，低质量或不确定窗口不会产生动作。

### Phase 6 — Live EEG to Simulation / 阶段 6：实时 EEG 到仿真闭环

- [ ] Select supported EEG hardware only after the offline decoder and protocol are stable. / 仅在离线解码器和实验协议稳定后选择 EEG 硬件。
- [ ] Integrate BrainFlow for acquisition and Lab Streaming Layer for synchronization and markers. / 使用 BrainFlow 采集，并以 LSL 完成同步与事件标记。
- [ ] Add per-user calibration, impedance or contact-quality gates, session checks, and drift monitoring. / 加入用户校准、电极接触质量门禁、会话检查与漂移监测。
- [ ] Separate target selection and execution confirmation into distinct EEG windows. / 将目标选择与执行确认拆分为独立 EEG 时间窗。
- [ ] Measure end-to-end latency, false activations, abstention rate, and user workload. / 测量端到端延迟、误触发率、拒识率与用户负担。
- [ ] Demonstrate live EEG control of the simulated G1 without changing downstream components. / 在不修改下游组件的前提下，以实时 EEG 控制仿真 G1。

**Exit criterion / 完成标准:** a measured, repeatable live EEG-to-G1-simulation loop supports select, confirm, cancel, and stop. / 建立可测量、可复现的实时 EEG 到 G1 仿真闭环，并支持四种核心意图。

### Phase 7 — Physical Unitree G1 Pilot / 阶段 7：宇树 G1 真机验证

- [ ] Integrate `unitree_sdk2_python` and `unitree_ros2` behind the existing G1 adapter. / 在现有 G1 Adapter 后接入 unitree_sdk2_python 与 unitree_ros2。
- [ ] Validate networking, DDS domains, joint mappings, cameras, clocks, and command frequencies without actuation. / 在不驱动关节的条件下验证网络、DDS Domain、关节映射、相机、时钟与命令频率。
- [ ] Require a physical emergency stop, supervised workspace, operator takeover, and written preflight checklist. / 强制要求实体急停、受控工作区、人工接管与书面预检清单。
- [ ] Progress through read-only observation, single-joint tests, scripted skills, VLA skills, and finally EEG authorization. / 依次完成只读观测、单关节测试、固定技能、VLA 技能和 EEG 授权。
- [ ] Keep balance, torque, velocity, collision, and workspace enforcement outside generative models. / 将平衡、力矩、速度、碰撞与工作空间约束保持在生成模型之外。
- [ ] Compare simulation and physical traces for the same task. / 对比同一任务的仿真与真机轨迹。

**Exit criterion / 完成标准:** under supervised laboratory conditions, sparse EEG intent authorizes a repeatable G1 manipulation task with deterministic stopping and operator takeover. / 在受控实验条件下，稀疏 EEG 意图可授权 G1 稳定完成操作任务，并具备确定性停止与人工接管。

### Phase 8 — Reproducible Research Platform / 阶段 8：可复现研究平台

- [ ] Publish versioned protocols, scenario suites, model cards, datasets, and benchmark reports. / 发布版本化实验协议、场景集、模型卡、数据集与基准报告。
- [ ] Support additional EEG devices, planners, policies, simulators, and Unitree embodiments through adapters. / 通过 Adapter 支持更多 EEG 设备、Planner、Policy、仿真器与宇树本体。
- [ ] Evaluate task success, latency, false activation, safety intervention, recovery, user workload, and agency separately. / 分别评估任务成功率、延迟、误触发、安全介入、恢复能力、用户负担与控制感。
- [ ] Add reproducible deployment profiles for CPU-only CI, local GPU, simulation, and supervised physical operation. / 为纯 CPU CI、本地 GPU、仿真与受监督真机运行建立可复现部署配置。
- [ ] Establish contribution, governance, security, privacy, and responsible-use policies. / 建立贡献、治理、安全、隐私与负责任使用政策。

**Exit criterion / 完成标准:** third parties can reproduce a benchmark and add one new component without modifying the Harness core. / 第三方能够复现基准，并在不修改 Harness 核心的情况下接入一个新组件。

## Initial Demonstration / 首个演示目标

The first demonstration will use four discrete intents—select, confirm, cancel, and stop—to authorize a simulated robot to pick a visually identified object and place it in a designated area.

首个演示使用选择、确认、取消和停止四种离散意图，授权仿真机器人抓取视觉识别到的物体，并将其放入指定区域。

## Scope / 项目边界

Synapse2Action is intended for research, education, and supervised prototyping. It is not a medical device and must not be used for diagnosis, treatment, life-critical control, or unsupervised operation around people.

Synapse2Action 面向科研、教学与有人监督的原型验证，不属于医疗器械，不得用于诊断、治疗、生命关键控制或在人群附近进行无人监督操作。

## Status / 当前状态

The project is at the early safety-kernel stage. A minimal deterministic Harness, mock planner, fake robot, rule-based verifier, and safety tests are available. No hardware integration, trained model, benchmark result, or safety certification is claimed yet.

项目当前处于安全内核早期阶段，已经具备最小确定性 Harness、Mock Planner、Fake Robot、规则验证器与安全测试。尚未宣称完成硬件集成、模型训练、基准结果或安全认证。

## Development / 开发

The core currently has no runtime dependencies. Run the deterministic test suite with Python 3.12 or newer:

当前核心没有运行时依赖。使用 Python 3.12 或更高版本运行确定性测试：

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

Run all hardware-free experiment scenarios and print a deterministic JSON report:

运行全部无设备实验场景，并输出确定性的 JSON 报告：

```bash
PYTHONPATH=src python3 -m synapse2action --demo
PYTHONPATH=src python3 -m synapse2action --navigation-demo
PYTHONPATH=src python3 -m synapse2action --navigation-demo --navigation-scenario experiments/navigation/04_diagonal_dynamic.json
PYTHONPATH=src python3 -m synapse2action --navigation-suite experiments/navigation --navigation-episode-directory artifacts/navigation-episodes
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --embedded-vla
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --record-vla-episode artifacts/navigation-episode.json
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --replay-vla-episode artifacts/navigation-episode.json
PYTHONPATH=src python3 -m synapse2action --export-vla-dataset artifacts/navigation-episodes/*.episode.json --vla-dataset-output artifacts/vla-dataset --validation-fraction 0.3
PYTHONPATH=src python3 -m synapse2action --train-vla-baseline artifacts/vla-dataset --vla-checkpoint artifacts/knn-vla.json
PYTHONPATH=src python3 -m synapse2action --train-vla-baseline artifacts/vla-dataset --vla-baseline-algorithm ridge --vla-checkpoint artifacts/ridge-vla.json
PYTHONPATH=src python3 -m synapse2action --train-vla-baseline artifacts/vla-dataset --vla-baseline-algorithm temporal-ridge --vla-checkpoint artifacts/temporal-ridge-vla.json
PYTHONPATH=src python3 -m synapse2action --train-vla-baseline artifacts/vla-dataset --vla-baseline-algorithm chunked-ridge --vla-checkpoint artifacts/chunked-ridge-vla.json
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --vla-checkpoint artifacts/knn-vla.json
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --vla-checkpoint artifacts/chunked-ridge-vla.json --vla-execution-horizon 1
PYTHONPATH=src python3 -m synapse2action --benchmark-vla-baseline artifacts/vla-dataset --benchmark-navigation-scenarios experiments/navigation --vla-checkpoint artifacts/knn-vla.json
PYTHONPATH=src python3 -m synapse2action --benchmark-vla-baseline artifacts/vla-dataset --benchmark-navigation-scenarios experiments/navigation --vla-checkpoint artifacts/ridge-vla.json
PYTHONPATH=src python3 -m synapse2action --cross-validate-vla-baseline artifacts/navigation-episodes/*.episode.json --cross-validation-output artifacts/ridge-loocv --benchmark-navigation-scenarios experiments/navigation --vla-baseline-algorithm ridge --output artifacts/ridge-loocv.json
PYTHONPATH=src python3 -m synapse2action --cross-validate-vla-baseline artifacts/navigation-episodes/*.episode.json --cross-validation-output artifacts/temporal-ridge-loocv --benchmark-navigation-scenarios experiments/navigation --vla-baseline-algorithm temporal-ridge --output artifacts/temporal-ridge-loocv.json
PYTHONPATH=src python3 -m synapse2action --cross-validate-vla-baseline artifacts/navigation-episodes/*.episode.json --cross-validation-output artifacts/chunked-ridge-loocv --benchmark-navigation-scenarios experiments/navigation --vla-baseline-algorithm chunked-ridge --vla-execution-horizon 1 --output artifacts/chunked-ridge-loocv.json
PYTHONPATH=src python3 -m synapse2action --cross-validate-vla-baseline artifacts/navigation-episodes/*.episode.json --cross-validation-output artifacts/chunked-ensemble-loocv --benchmark-navigation-scenarios experiments/navigation --vla-baseline-algorithm chunked-ridge --vla-execution-horizon 1 --vla-temporal-ensemble-decay 0.75 --output artifacts/chunked-ensemble-loocv.json
PYTHONPATH=src python3 -m synapse2action --vla-navigation-demo --robot-transport loopback --output artifacts/vla-loopback.json
PYTHONPATH=src python3 -m synapse2action --demo-html demo.html --output demo.json
PYTHONPATH=src python3 -m synapse2action --demo-scenario experiments/demos/blue_block.json --demo-html blue-demo.html
PYTHONPATH=src python3 -m synapse2action --demo-suite experiments/demos --artifact-directory artifacts/demo-suite --output artifacts/demo-suite.json
PYTHONPATH=src python3 -m synapse2action --demo-scenario experiments/demos/red_cube.json --record-eeg artifacts/red-cube-eeg.json --output artifacts/recorded-run.json
PYTHONPATH=src python3 -m synapse2action --demo-scenario experiments/demos/red_cube.json --replay-eeg artifacts/red-cube-eeg.json --output artifacts/replayed-run.json
PYTHONPATH=src python3 -m synapse2action
PYTHONPATH=src python3 -m synapse2action --output report.json
PYTHONPATH=src python3 -m synapse2action --intent-directory experiments/intent_streams
PYTHONPATH=src python3 -m synapse2action --monte-carlo-config experiments/monte_carlo/false_activation.json
```

The `--demo` command runs the complete hardware-free happy path: seeded noisy SSVEP samples, frequency-based intent decoding, fake perception and world state, mock planning, scripted policy, a deterministic 2D tabletop robot, and independent final-state verification.

`--demo` 命令运行完整的无设备 happy path：固定 seed 的带噪 SSVEP 样本、频率意图解码、Fake Perception 与 World、Mock Planner、Scripted Policy、确定性二维桌面机器人及独立终态验证。

Navigation scenarios are data-driven JSON files under `experiments/navigation/`. The bundled ten-scenario suite covers clear paths, centered and offset obstacles, horizontal, vertical, diagonal, and reverse travel, short sensor range, and obstacle activation at different times. `--navigation-suite` runs every scenario through the serialized VLA path and can write one training episode per scenario. / 导航场景由 `experiments/navigation/` 下的 JSON 驱动。内置十场景 suite 覆盖无障碍路径、居中与偏置障碍、横向、纵向、斜向与反向移动、短传感距离及不同障碍激活时刻。`--navigation-suite` 通过序列化 VLA 路径运行所有场景，并可为每个场景写出一条训练 episode。

`--navigation-demo` runs a confirmed A-to-B task as a real closed loop. A policy observation combines the task instruction with a timestamped `SensorFrame` containing a deterministic robot-centered 360-degree `mono8` local occupancy raster, base proprioception, pose, and locally perceived obstacles. The policy turns the latest multimodal observation into a short velocity action chunk, the robot adapter applies it, and an independent verifier checks both arrival and stopped base state. The scenario begins on a clear path, introduces a crate after 600 ms, and proves that the policy replans from new observations instead of following a frozen startup trajectory. / `--navigation-demo` 将确认后的 A 到 B 任务作为真实闭环运行。Policy Observation 将任务文本与带时间戳的 `SensorFrame` 组合；帧内包含以机器人为中心、覆盖 360 度局部范围的确定性 `mono8` occupancy 栅格、底盘 proprioception、位姿和局部障碍物。Policy 将最新多模态观测转换成短时速度 Action Chunk，经 Robot Adapter 执行，独立 Verifier 同时检查到达和底盘停止状态。场景开始时道路畅通，在 600ms 后出现箱体，用于证明策略会依据新观测重规划，而不是执行启动时冻结的轨迹。

`--vla-navigation-demo` runs the same dynamic scenario through the byte-level VLA adapter. Every multimodal observation is JSON-serialized with base64 camera bytes, processed by a deterministic local inference backend, and strictly decoded from model-style JSON into an `ActionChunk`. / `--vla-navigation-demo` 通过字节级 VLA Adapter 运行同一动态场景。每帧多模态 Observation 都会序列化为 JSON（相机 bytes 使用 base64），经确定性本地推理 Backend 处理，再从模型式 JSON 严格解析为 `ActionChunk`。

Use `--embedded-vla` to send the same reset and inference payloads over real loopback HTTP. An external service can replace it with `--vla-base-url http://localhost:9000/v1`; the optional API key is read from `VLA_API_KEY`. / 使用 `--embedded-vla` 可让相同的 reset 与 inference payload 经过真实 loopback HTTP。外部服务可通过 `--vla-base-url http://localhost:9000/v1` 替换内置服务；可选 API Key 从 `VLA_API_KEY` 读取。

Use `--record-vla-episode` to persist every serialized observation/action pair, then use `--replay-vla-episode` to reproduce the run without an inference service. Replay is step-exact: a changed task or observation fails instead of silently returning an unrelated recorded action. / 使用 `--record-vla-episode` 可持久化每一组序列化 Observation/Action，随后用 `--replay-vla-episode` 在没有推理服务时复现运行。回放要求逐步精确一致；任务或观测发生变化时会失败，不会静默返回无关的历史动作。

Use `--export-vla-dataset` with two or more episode files to create `manifest.json`, `train.jsonl`, and `validation.jsonl`. Each sample preserves the camera raster, base state, goal, and structured locally perceived obstacles from the same observation. Splitting happens at episode level before frames are expanded, so adjacent observations from one trajectory cannot leak across train and validation. The bundled benchmark uses a 30% split: seven training episodes and three held-out episodes. / 使用 `--export-vla-dataset` 输入两个或更多 episode 文件，可生成 `manifest.json`、`train.jsonl` 与 `validation.jsonl`。每条样本会保留同一 Observation 的相机栅格、底盘状态、目标及结构化局部障碍物。系统先按 episode 划分，再展开帧，因此同一轨迹的相邻 Observation 不会泄漏到 train 和 validation 两侧。内置 benchmark 使用 30% 划分，即七条训练 episode 与三条 held-out episode。

`--train-vla-baseline` trains a deterministic normalized 1-nearest-neighbor behavior-cloning baseline from `train.jsonl`, evaluates it on `validation.jsonl`, and writes a standalone checkpoint. Supplying that checkpoint to `--vla-navigation-demo` runs the learned policy through the same VLA adapter and robot loop. This is a dependency-free imitation baseline, not ACT or SmolVLA. / `--train-vla-baseline` 使用 `train.jsonl` 训练确定性的归一化 1-NN behavior-cloning 基线，在 `validation.jsonl` 上评测并写出独立 checkpoint。将 checkpoint 传给 `--vla-navigation-demo` 后，学习策略会通过同一 VLA Adapter 与机器人闭环运行。这是零依赖 imitation baseline，不是 ACT 或 SmolVLA。

Select `--vla-baseline-algorithm ridge` to train a continuous Ridge behavior-cloning model over relative goal geometry, base velocity, and camera occupancy/centroid features. Checkpoint format is detected automatically at inference. / 使用 `--vla-baseline-algorithm ridge` 可训练连续 Ridge behavior-cloning 模型，输入包括相对目标几何、底盘速度以及相机占用率/质心特征；推理时会自动识别 checkpoint 格式。

Select `temporal-ridge` to add one-step camera and obstacle deltas while keeping pose and velocity features single-frame. Its version-2 checkpoint records `history_steps` and a separate temporal regularization multiplier. The temporal block is intentionally treated as a small residual: weak regularization improves offline MAE but destabilizes closed-loop rollouts. / 选择 `temporal-ridge` 可加入一阶相机与障碍变化量，同时保持位姿和速度为单帧特征。其 version-2 checkpoint 会记录 `history_steps` 与独立 temporal regularization multiplier。时序块被有意限制为小幅 residual；过弱的正则虽然会改善离线 MAE，却会破坏闭环 rollout 稳定性。

Select `chunked-ridge` to train a version-3 checkpoint that predicts four future 100 ms commands from each observation. Future targets are built within episode boundaries and repeat the final action only for end padding. Prediction horizon and robot execution horizon are separate: full four-command open-loop execution completes 8/10 leave-one-scenario-out folds, while `--vla-execution-horizon 1` executes one predicted command before observing again and completes 10/10 using the exact same checkpoints. This difference is reported explicitly; it is not an offline-metric change. / 选择 `chunked-ridge` 可训练 version-3 checkpoint，使每次 Observation 预测未来四条 100 ms command。未来目标不会跨越 episode 边界，末尾仅使用最后一条动作进行 padding。预测 horizon 与机器人执行 horizon 相互独立：完整四命令 open-loop 执行在 leave-one-scenario-out 中为 8/10；使用 `--vla-execution-horizon 1` 后，每执行一条预测命令就重新观测，在完全相同的 checkpoint 上达到 10/10。报告会明确区分这两项结果，而不是把它伪装成离线指标变化。

Add `--vla-temporal-ensemble-decay 0.75` to blend overlapping chunk predictions for the current command. Ensembling is perception-gated: when any obstacle is visible, only the newest chunk is used, preventing stale clear-path predictions from diluting a new avoidance action. On the ten-fold benchmark it preserves 10/10 success and reduces the command-weighted mean translational velocity delta from `0.01251` to `0.01234 m/s`. / 加入 `--vla-temporal-ensemble-decay 0.75` 后，可融合多个重叠 chunk 对当前命令的预测。Ensemble 受 perception gate 约束：只要局部视野中存在障碍，就仅采用最新 chunk，避免旧的无障碍预测稀释新的避障动作。十折 benchmark 中成功率保持 10/10，按相邻命令数量加权的平均平移速度变化从 `0.01251` 降至 `0.01234 m/s`。

`--robot-transport loopback` moves both perception and execution across the same versioned wire boundary intended for a future ROS2 or chassis-SDK adapter. The driver responds to serialized `observe` requests with pose, visible obstacles, camera bytes, and proprioception, then accepts serialized `base_velocity` commands and returns acknowledgements with measured state. Loopback owns sensing, motion integration, and collision rejection, so the complete intent → confirmation → observation → VLA → action chunk → robot feedback path runs without hardware. / `--robot-transport loopback` 会让感知与执行同时跨过带版本的 wire boundary；未来 ROS2 或底盘 SDK adapter 复用同一接口。Driver 对序列化 `observe` 请求返回位姿、可见障碍、相机字节及本体状态，再接收 `base_velocity` 指令并返回带实测状态的 ACK。Loopback 负责感知、运动积分和碰撞拒绝，因此无需设备也能跑通“意图 → 确认 → Observation → VLA → Action Chunk → 机器人反馈”全链路。

`--benchmark-vla-baseline` automatically recognizes KNN and Ridge checkpoints, verifies that checkpoint episode IDs exactly match the train split, computes offline metrics on validation samples, maps validation episode sources back to their navigation scenarios, and reports held-out closed-loop success, goal error, and execution failure detail. Offline MAE and closed-loop success are reported separately because a smaller one-step error does not prove that a policy can recover from its own rollout distribution. / `--benchmark-vla-baseline` 会自动识别 KNN 与 Ridge checkpoint，验证 checkpoint episode ID 与 train split 精确一致，在 validation 样本上计算离线指标，将 validation episode 来源映射回导航场景，并报告 held-out 闭环成功率、终点误差和执行失败原因。离线 MAE 与闭环成功率分开报告，因为更小的单步误差不能证明策略能从自身 rollout 分布中恢复。

`--cross-validate-vla-baseline` performs leave-one-scenario-out evaluation. Every episode becomes the explicit validation split once; the model is retrained from the other episodes, then run closed-loop on the unseen scenario. Each fold keeps its dataset manifest and checkpoint under `--cross-validation-output`, while the aggregate report contains sample-weighted offline metrics and cross-scenario closed-loop success. On the bundled ten-scenario suite, temporal Ridge completes 10/10 folds with velocity MAE `0.01658`, static Ridge completes 10/10 with `0.01851`, and KNN completes 2/10 with `0.08412`. / `--cross-validate-vla-baseline` 执行 leave-one-scenario-out 评测。每条 episode 都会轮流成为一次显式 validation split；模型仅使用其余 episode 重新训练，再在未见场景中闭环运行。每折的 dataset manifest 与 checkpoint 会保存在 `--cross-validation-output`，汇总报告同时给出按样本加权的离线指标和跨场景闭环成功率。内置十场景 suite 中，Temporal Ridge 为 10/10、速度 MAE `0.01658`，静态 Ridge 为 10/10、`0.01851`，KNN 为 2/10、`0.08412`。

The planner selects a typed skill; the policy expands it into `approach`, `grasp`, `transport`, and `release` steps; the robot executes only the supplied trajectory. / Planner 选择类型化技能，Policy 将其展开为 `approach`、`grasp`、`transport` 与 `release`，Robot 只执行收到的轨迹。

End-to-end demo scenarios are data-driven JSON files under `experiments/demos/`; object identity, positions, destination, decoder threshold, and neural windows can be changed without editing Python. / 端到端 Demo 使用 `experiments/demos/` 下的数据驱动 JSON；无需修改 Python 即可调整对象、位置、目标区、解码阈值和神经窗口。

The bundled suite covers completed pick-and-place, cancellation, and emergency-stop outcomes decoded from numeric SSVEP signals. / 内置套件覆盖从数值 SSVEP 信号解码出的抓取放置成功、取消及急停终态。

The `--demo-suite` command runs every scenario and emits aggregate metrics plus one JSON/HTML pair per task. / `--demo-suite` 可批量运行全部场景，输出汇总指标，并为每项任务生成一组 JSON/HTML 产物。

Raw numeric EEG windows can be saved with `--record-eeg` and replayed with `--replay-eeg`; replay uses the stored samples rather than regenerating signals. / 使用 `--record-eeg` 可保存原始数值 EEG 窗口，`--replay-eeg` 会直接回放已保存样本，而不是重新生成信号。

An OpenAI-compatible Chat Completions planner can replace `MockPlanner` without changing downstream components:

可使用 OpenAI-compatible Chat Completions Planner 替换 `MockPlanner`，无需修改下游组件：

```bash
PYTHONPATH=src python3 -m synapse2action --demo \
  --planner-base-url http://localhost:8000/v1 \
  --planner-model your-model-name
```

The API key is read from `OPENAI_API_KEY` by default and is never written to reports. / API Key 默认从 `OPENAI_API_KEY` 读取，且不会写入实验报告。

To verify the actual HTTP boundary without an external model, run the temporary loopback-only compatible server. It starts on an ephemeral port and shuts down before the command exits:

无需外部模型时，可用临时 loopback-only 兼容服务验证真实 HTTP 边界。服务使用临时端口，并在命令结束前关闭：

```bash
PYTHONPATH=src python3 -m synapse2action --demo --embedded-planner
```

The bundled suite covers successful execution, cancellation, emergency stop, invented skills, simulated robot timeout, and execution without confirmation. Scenario files live in `experiments/scenarios/` and require no model, simulator, EEG device, or robot.

内置实验覆盖成功执行、取消、急停、虚构技能、模拟机器人超时及未经选择直接确认。场景文件位于 `experiments/scenarios/`，无需模型、仿真器、EEG 设备或机器人。

See [`docs/experiments.md`](docs/experiments.md) for the staged experiment matrix, metrics, and acceptance gates. / 分阶段实验矩阵、指标及验收门槛见 [`docs/experiments.md`](docs/experiments.md)。

## License / 许可证

The project license has not been selected yet. Dependencies and model weights may use different licenses and will be reviewed before implementation begins.

项目许可证尚未确定。依赖库与模型权重可能采用不同许可证，将在开始实现前逐项审查。
