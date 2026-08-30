# References and Dependency Register / 参考材料与依赖登记

This register records the libraries, models, datasets, papers, and external systems that Synapse2Action directly uses or materially learns from. A citation here does not imply that an upstream claim was independently reproduced. The **Relationship** column states the actual evidence boundary.

本登记表记录 Synapse2Action 直接使用或实质参考的库、模型、数据集、论文与外部系统。列入本表不表示上游结论已被本项目独立复现；实际证据边界以 **关系** 一栏为准。

## Relationship labels / 关系标签

| Label | Meaning |
|---|---|
| Integrated / 已集成 | Code or protocol is exercised by the current repository. / 当前仓库已运行其代码或协议。 |
| Staged / 已暂存 | Source or weights are pinned locally, but the complete path has not passed acceptance. / 已固定源码或权重，但完整链路尚未验收。 |
| Evaluated / 已评测 | Used as an experimental comparison or evidence source. / 用作实验对照或证据来源。 |
| Reference / 仅参考 | Influenced design or roadmap; no integration claim. / 影响设计或路线图，不声称已集成。 |

## Core software and model stack / 核心软件与模型栈

| Project | Relationship | Use in Synapse2Action | Version or pin | Primary source |
|---|---|---|---|---|
| Python | Integrated / 已集成 | Harness, contracts, experiments, adapters, and reports | `>=3.12` | [python.org](https://www.python.org/) |
| NumPy | Integrated / 已集成 | Signal processing, trajectories, observations, and reports | Environment-managed | [numpy.org](https://numpy.org/) |
| SciPy | Integrated / 已集成 | EEG filtering and signal processing | Environment-managed | [scipy.org](https://scipy.org/) |
| scikit-learn | Integrated / 已集成 | EEG and VLA comparison baselines and metrics | Environment-managed | [scikit-learn.org](https://scikit-learn.org/) |
| PyTorch | Integrated / 已集成 | SmolVLA training and inference | `2.7.1+cpu` in `simulation/vla.lock.json` | [pytorch.org](https://pytorch.org/) |
| Transformers | Integrated / 已集成 | VLM/VLA model dependency through LeRobot | `5.5.4` in `simulation/vla.lock.json` | [huggingface/transformers](https://github.com/huggingface/transformers) |
| LeRobot | Integrated / 已集成 | Dataset export, training, preprocessing, and SmolVLA runtime | `0.6.1` | [huggingface/lerobot](https://github.com/huggingface/lerobot) |
| SmolVLA | Integrated / 已集成 | Current language-conditioned G1 simulation policy baseline | `lerobot/smolvla_base`, 450,046,176 parameters | [Model card](https://huggingface.co/lerobot/smolvla_base) |
| ONNX Runtime | Integrated / 已集成 | Unitree RL policy inference | Environment-managed | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) |
| OpenPI | Staged / 已暂存 | Candidate `Policy` backend, data transforms, normalization, action-chunk inference, and policy-server reference | `215abfb217dbac7d5f1273282331b9b1866c0479` | [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) |
| OpenAI-compatible API | Integrated / 已集成 | Replaceable structured Planner provider boundary | Protocol, not one vendor SDK | [OpenAI API reference](https://platform.openai.com/docs/api-reference) |

## Planner models evaluated / 已评测 Planner 模型

| Model route | Relationship | Evidence boundary | Local evidence |
|---|---|---|---|
| DeepSeek V4 Flash through `yuesheng-vllm` | Evaluated / 已评测 | Accepted only for the recorded provider identity and structured Planner suite | `reports/planners/yuesheng-vllm-model.json` |
| Qwen3.8-Flash-Next through `qwen-vllm` | Evaluated / 已评测 | Accepted only for the recorded self-hosted route and Planner suite | `reports/planners/qwen-vllm-qwen38-flash-next.json` |
| GLM-5.3 through BigModel | Evaluated / 已评测 | Optional Planner; fenced-output normalization remains visible in the report | `reports/planners/bigmodel-glm-5.3.json` |
| DeepSeek-V4-Flash-0731 through `rtxpro-vllm` | Evaluated / 已评测 | Non-blocking unavailable alternative; retained smoke requests returned HTTP 502 | `docs/pre-simulation-audit.md` |

## Robot, simulation, and middleware / 机器人、仿真与中间件

| Project | Relationship | Use in Synapse2Action | Version or pin | Primary source |
|---|---|---|---|---|
| MuJoCo | Integrated / 已集成 | G1 dynamics, cameras, contacts, and task verification | Environment-managed | [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco) |
| Unitree SDK2 Python | Integrated / 已集成 | Official DDS message types and SDK2 adapter | `65691c8a8bc53b98d3976dba4dbf9d5d20b2e7f5` | [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) |
| Unitree SDK2 C++ | Integrated / 已集成 | Official low-level command and state contract | `9754cd153af3da471b0fe5f3aa535e426fb11db3` | [unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2) |
| unitree_mujoco | Integrated / 已集成 | Official SDK2-to-MuJoCo bridge | `4134cb5dc7ff1ba7f484deda48b5274b58694519` | [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) |
| unitree_rl_lab | Integrated / 已集成 | Exported G1 lower-body velocity policy and deployment configuration | `4960b84732b0c2ec593dccbfe963fda1bcd7b1e3` | [unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab) |
| Cyclone DDS | Integrated / 已集成 | DDS transport used by the Unitree simulation/control path | `5041f3560c088c99e5088b2b8520b69169621196` | [eclipse-cyclonedds](https://github.com/eclipse-cyclonedds/cyclonedds) |
| ROS 2 / rclpy | Integrated / 已集成 | Optional ROS 2 transport and message boundary | Deployment-managed | [ros2/rclpy](https://github.com/ros2/rclpy) |
| NVIDIA Isaac GR00T | Staged / 已暂存 | Candidate humanoid VLA backend; full Ubuntu/CUDA path remains unaccepted | `51d4c89f72fda44cbf77285c6a8114b52676b8a1` | [NVIDIA/Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) |
| GR00T Whole-Body Control | Staged / 已暂存 | G1 whole-body deployment and VLA-to-controller reference | `a0732b642c0333077e127a2f56ab0014c196bca4` | [NVlabs/GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl) |
| GEAR-SONIC v1.1 | Staged / 已暂存 | Whole-body latent controller candidate; ONNX files are checksum-pinned | See `simulation/groot_sonic.lock.json` | [Model card](https://huggingface.co/nvidia/GEAR-SONIC) |

## Intent and biosignal stack / 意图与生物信号栈

| Project | Relationship | Use in Synapse2Action | Evidence boundary | Primary source |
|---|---|---|---|---|
| BrainFlow | Integrated / 已集成 | Synthetic/playback acquisition boundary and board-independent API | No physical headset acceptance | [brainflow-dev/brainflow](https://github.com/brainflow-dev/brainflow) |
| Lab Streaming Layer / pylsl | Integrated / 已集成 | Timestamped stream and marker synchronization | Synthetic live path only | [sccn/labstreaminglayer](https://github.com/sccn/labstreaminglayer) |
| WFDB Python | Integrated / 已集成 | Reading PhysioNet-hosted MAMEM records | Offline public data | [MIT-LCP/wfdb-python](https://github.com/MIT-LCP/wfdb-python) |
| MAMEM Experiment 3 | Evaluated / 已评测 | Cross-subject SSVEP decoding and replay | No idle class; not an idle false-activation benchmark | [PhysioNet MAMEM EEG SSVEP](https://physionet.org/content/mssvepdb/) |
| MAMEM Experiment 2 | Evaluated / 已评测 | 256-channel SSVEP experiment with protocol rest windows | First held-out release gate failed | [MAMEM project](https://www.mamem.eu/) |

## Roadmap candidates not integrated / 尚未集成的路线图候选

These names appear in project planning but are not current dependencies. They remain here so that a roadmap mention cannot be mistaken for implementation.

以下项目出现在路线图或候选架构中，但不是当前依赖。保留登记是为了防止把路线图名称误读成已完成实现。

| Project | Relationship | Candidate role | Primary source |
|---|---|---|---|
| OpenBCI | Reference / 仅参考 | Candidate physical EEG hardware | [OpenBCI documentation](https://docs.openbci.com/) |
| MNE-Python | Reference / 仅参考 | Candidate EEG preprocessing and analysis | [mne-tools/mne-python](https://github.com/mne-tools/mne-python) |
| pyRiemann | Reference / 仅参考 | Candidate Riemannian EEG decoding baseline | [pyRiemann/pyRiemann](https://github.com/pyRiemann/pyRiemann) |
| Braindecode | Reference / 仅参考 | Candidate deep EEG decoding baseline | [braindecode/braindecode](https://github.com/braindecode/braindecode) |
| MoveIt 2 | Reference / 仅参考 | Candidate arm motion-planning and collision layer | [moveit/moveit2](https://github.com/moveit/moveit2) |
| ManiSkill | Reference / 仅参考 | Candidate manipulation simulation benchmark | [haosulab/ManiSkill](https://github.com/haosulab/ManiSkill) |

## Papers and technical foundations / 论文与技术依据

| Work | Relationship | What the project takes from it | Source |
|---|---|---|---|
| *SmolVLA: A Vision-Language-Action Model for Affordable and Efficient Robotics* | Integrated / 已集成 | Compact VLA, flow-matching action expert, community LeRobot data, asynchronous inference motivation | [arXiv:2506.01844](https://arxiv.org/abs/2506.01844) |
| *LeRobot: State-of-the-art Machine Learning for Real-World Robotics in Pytorch* | Integrated / 已集成 | Reproducible datasets, policy training, evaluation, and hardware adapters | [LeRobot repository](https://github.com/huggingface/lerobot) |
| *NVIDIA Isaac GR00T N1: An Open Foundation Model for Generalist Humanoid Robots* | Staged / 已暂存 | Humanoid VLA architecture and cross-embodiment training reference | [arXiv:2503.14734](https://arxiv.org/abs/2503.14734) |
| *SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control* | Staged / 已暂存 | Shared latent motion representation and whole-body control | [Project and paper](https://nvlabs.github.io/GEAR-SONIC/) |
| *π0: A Vision-Language-Action Flow Model for General Robot Control* | Reference / 仅参考 | Flow-matching VLA and cross-embodiment policy design | [Official paper](https://www.physicalintelligence.company/download/pi0.pdf) |
| *π0.5: A Vision-Language-Action Model with Open-World Generalization* | Reference / 仅参考 | Unified high-level subtask prediction and low-level action inference | [Official paper](https://www.physicalintelligence.company/download/pi05.pdf) |
| *RoboArena: Distributed Real-World Evaluation of Generalist Robot Policies* | Reference / 仅参考 | Multi-site physical evaluation methodology and evidence that real-world policy ranking requires repeated, distributed trials | [Proceedings of Machine Learning Research](https://proceedings.mlr.press/v270/karen25a.html) |
| *OpenVLA: An Open-Source Vision-Language-Action Model* | Reference / 仅参考 | Generalist language-conditioned action modeling and comparison baseline | [openvla/openvla](https://github.com/openvla/openvla) |
| *VoxPoser: Composable 3D Value Maps for Robotic Manipulation with Language Models* | Reference / 仅参考 | Language-conditioned geometric planning and explicit motion-planner separation | [huangwl18/VoxPoser](https://github.com/huangwl18/VoxPoser) |
| *Canonical Correlation Analysis* and Filter-Bank CCA for SSVEP | Integrated / 已集成 | Classical SSVEP decoding baseline and primary filter-bank decoder | [CCA overview](https://doi.org/10.2307/2333955) |

## Design references and related systems / 设计参考与相关系统

| Project | Relationship | Relevance | Source |
|---|---|---|---|
| VLAPilot | Reference / 仅参考 | Explicit plan, VLA skill scheduling, stepwise execution, and visual verification | [FutianLabs/VLAPilot](https://github.com/FutianLabs/VLAPilot) |
| KIOS | Reference / 仅参考 | LLM-generated behavior trees, registered robot skills, and feedback-driven replanning | [ProNeverFake/kios](https://github.com/ProNeverFake/kios) |
| Assistron | Reference / 仅参考 | Shared autonomy with off-the-shelf VLA policies | [mousecpn/Assistron](https://github.com/mousecpn/Assistron) |
| ROSA | Reference / 仅参考 | Natural-language interaction with ROS systems | [nasa-jpl/rosa](https://github.com/nasa-jpl/rosa) |
| OpenWBC | Reference / 仅参考 | G1 teleoperation and whole-body VLA data collection | [jiachengliu3/OpenWBC](https://github.com/jiachengliu3/OpenWBC) |

## Industrial safety and qualification references / 工业安全与准入参考

| Standard or source | Relationship | Relevance | Source |
|---|---|---|---|
| ISO 10218-1 and ISO 10218-2 | Reference / 仅参考 | Industrial robot and robot-cell safety requirements; informs the separation between probabilistic policy proposals and deterministic safety authority | [ISO robotics standards catalogue](https://www.iso.org/ics/25.040.30/x/) |

## Reproducibility index / 可复现性索引

| Scope | Authoritative local record |
|---|---|
| Unitree repositories | `simulation/unitree.lock.json` |
| SmolVLA/LeRobot runtime | `simulation/vla.lock.json` |
| GR00T/SONIC source and weights | `simulation/groot_sonic.lock.json` |
| OpenPI source | `simulation/openpi.lock.json` |
| Planner evidence | `reports/planners/` |
| Experiment methodology and gates | `docs/experiments.md` |
| Current limitations and decisions | `docs/current-challenges.md` |

## Maintenance rule / 维护规则

Every new external library, model, dataset, paper, or materially reused project must be added here in the same change that introduces it. Record the relationship honestly: reading a paper is not integration, a successful import is not a closed-loop result, simulation is not physical evidence, and an upstream benchmark is not a Synapse2Action result.

以后每次引入外部库、模型、数据集、论文或实质参考项目，必须在同一改动中登记。关系必须如实标注：读过论文不等于完成集成，成功 import 不等于闭环通过，仿真不等于真机证据，上游 Benchmark 也不属于 Synapse2Action 自身成绩。
