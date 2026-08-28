# Hardware-Free Experiment Plan / 无设备实验计划

## Purpose / 目标

Every experiment must isolate one replaceable layer while keeping the remaining
pipeline deterministic. A result is valid only when its inputs, component
versions, trace, expected outcome, and failure reason can be replayed.

每项实验只替换一层，其余管线保持确定性。只有输入、组件版本、执行轨迹、预期结果与失败原因均可重放，实验结果才有效。

## Experiment ladder / 实验阶梯

| Level | Variable under test | Deterministic substitute | Required measurements |
|---|---|---|---|
| E0 Safety kernel | State transitions and invariants | All components mocked | illegal-transition rejection, execution count, final state, trace equality |
| E1 Synthetic intent | noise, confidence, timing, false activation | recorded intent generator | accuracy, abstention, false activations, intent latency |
| E2 Planner | schema-compliant task planning | fixed world state and fake robot | schema compliance, invented skills, unsafe-plan rejection, latency |
| E3 Policy | bounded action generation | scripted planner and simulated robot | action-limit violations, task success, timeout, recovery |
| E4 Robot simulation | dynamics and control adapter | scripted policy | completion, collision, watchdog stops, control latency |
| E5 End-to-end simulation | interactions between all software layers | synthetic or recorded EEG | task success, false activation, stop latency, interventions |

## E0 bundled scenarios / 已内置的 E0 场景

1. Confirmed target completes exactly one action.
2. Cancellation produces no action.
3. Emergency stop preempts the active state.
4. An invented skill is rejected before the robot boundary.
5. A simulated robot timeout fails independent verification.
6. Confirmation without selection is rejected.

## Next executable experiments / 下一批可执行实验

- Generate synthetic intent streams with configurable confusion, abstention, jitter, and duplicate events.
- Inject stale targets, missing arguments, malformed values, planner exceptions, and delayed responses.
- Add a virtual clock for deterministic planner, policy, robot, and stop timeouts.
- Define a small fake world containing colored cubes, a drop zone, occupancy, and object revisions.
- Add seeded randomized sequences and assert that no unconfirmed action reaches the robot.
- Replay every failed randomized run as a fixed regression scenario.

The initial Monte Carlo experiment generates one million intent windows and compares the bare state machine against confirmation-window, refractory, and repeated-evidence gating. It intentionally uses only false activations, so every executed action is unauthorized.

首个 Monte Carlo 实验生成一百万个意图窗口，对比裸状态机与“确认时间窗 + refractory + 多次独立证据”门控。实验中只有误触发，因此任何实际执行都属于未授权动作。

## Acceptance gates / 验收门槛

- Safety scenarios: 100% pass; no statistical tolerance.
- Deterministic replay: byte-identical report for identical scenario and version.
- Unconfirmed execution and unknown-skill execution: exactly zero.
- Emergency-stop propagation: measured separately at each layer; thresholds are set before integration.
- Probabilistic components: report confidence intervals and seeds, never only a mean score.

The initial CLI report deliberately excludes wall-clock timestamps and measured
duration so deterministic equality can be tested. Timing experiments will use a
virtual clock until a real integration layer is introduced.

初始 CLI 报告刻意不包含墙钟时间和实测耗时，以便验证确定性一致。接入真实集成层前，所有时序实验均使用虚拟时钟。

## Context-bound authorization / 上下文绑定授权

The Harness plans and validates immediately after target selection, then exposes the stored pending action for review. Confirmation authorizes that concrete skill and argument set; planning never happens after the user has already confirmed. Planner refusal or invalid output terminates before the confirmation gate and can never reach the robot.

Harness 在目标选择后立即规划并校验，然后将不可变的待执行动作暴露给审阅阶段。确认授权的是这组具体技能和参数；系统不会让用户先确认、再生成计划。Planner 拒绝或非法输出会在确认门之前终止，永远不会抵达机器人。

An optional deterministic challenge binds confirmation to a target, target revision, and expiry time. Challenges are single-use and reject expiry, replay, unknown tokens, and world-state revision drift. The token is a reproducible experiment identifier, not a cryptographic secret. This mechanism prevents stale or mismatched confirmation; it does not prove that a decoded EEG confirmation was intentional.

可选的确定性 challenge 将确认绑定到目标、目标版本和有效期。Challenge 只能消费一次，并拒绝过期、重放、未知 token 与世界状态版本漂移。该 token 是可复现实验标识，不是密码学秘密。它能阻止过期或错位确认，但不能证明 EEG 解码出的确认确实来自用户意图。

## Fake world / 虚拟世界状态

The fake world stores object identity, revision, observation time, position, occupancy, and reachability. The Harness validates the selected snapshot again immediately before confirmation. Movement, removal, occupancy changes, and stale observations therefore produce no robot action.

Fake World 保存对象身份、版本、观测时间、位置、占用和可达性。Harness 会在确认前重新校验所选快照，因此物体移动、消失、占用变化和观测过期均不会产生机器人动作。

## Typed skill registry / 类型化技能注册表

Every executable skill declares its exact argument schema, deterministic timeout, risk level, precondition, and success condition. Unknown skills, missing or extra arguments, wrong types, target substitution, and over-budget completion are rejected or failed without trusting planner or robot self-reporting.

每个可执行技能声明精确参数 Schema、确定性超时、风险等级、前置条件和成功条件。未知技能、参数缺失或多余、类型错误、目标偷换以及超预算完成均会被拒绝或判定失败，不信任 Planner 或 Robot 的自报结果。

The current synchronous fake robot reports virtual duration after execution; an over-budget result triggers `stop`. This validates policy and trace semantics, but real timeout preemption still requires an asynchronous executor and virtual clock.

当前同步 Fake Robot 在执行返回后报告虚拟耗时，超预算会触发 `stop`。这能验证策略与轨迹语义，但真实超时抢占仍需要异步执行器和虚拟时钟。

## E4/E5 Unitree SmolVLA acceptance / Unitree SmolVLA 验收

The hardware-free G1 manipulation experiment uses the official Unitree SDK2 bridge, the `unitree_rl_lab` G1 lower-body policy, MuJoCo dynamics, LeRobot 0.6.1, and a locally trained SmolVLA checkpoint. Five timing-varied, independently accepted episodes provide 560 training frames; the final 140-frame episode is held out. With diffusion sampling fixed to seed 0, the accepted checkpoint reports held-out overall MSE `0.01486` and waist/arm MSE `0.03654`, compared with `0.16516` for the earlier single-episode baseline. Two independent evaluator runs produced byte-identical reports. Offline error is only a deployment gate and never substitutes for rollout acceptance.

无设备 G1 操作实验使用官方 Unitree SDK2 Bridge、`unitree_rl_lab` G1 下肢策略、MuJoCo 动力学、LeRobot 0.6.1 和本地训练的 SmolVLA checkpoint。五条独立验收且时序不同的 episode 中，560 帧用于训练，最后 140 帧完全留出。固定 diffusion sampling seed 为 0 后，通过质量门的 checkpoint 在 held-out 数据上整体 MSE 为 `0.01486`，腰部/双臂 MSE 为 `0.03654`；早期单 episode 基线为 `0.16516`。两次独立评估生成了字节完全一致的报告。离线误差只作为部署门，不代替闭环验收。

The online acceptance keeps three boundaries separate: SmolVLA provides 3 Hz action chunks, a 500 Hz projector blends bounded residuals into the validated C++ behavior for nine waist/arm joints, and the official SDK2/RL stack owns balance and low-level control. Camera acquisition time is included in end-to-end chunk latency, and later chunks are inferred concurrently. Release requires prior lift, full object support inside the tray footprint, and a lowered object. Functional and realtime gates must both pass; acceptance now requires a measured non-zero counterfactual VLA joint-target contribution.

在线验收严格分离三层边界：SmolVLA 以 3Hz 提供 Action Chunk，500Hz 投影器把受限残差混入 C++ Behavior 的九个腰部/手臂关节目标，官方 SDK2/RL 栈继续拥有平衡与低层控制权。相机采集耗时计入 chunk 端到端时延，后续 chunk 并发推理。释放必须同时满足“已抬升、物体底面完整进入托盘、已下降”。功能门与实时门必须同时通过，且验收要求测得非零的 VLA 关节目标反事实贡献。

Authoritative local artifacts are `reports/training/smolvla-g1-suite-heldout.json`, `reports/simulation/g1-smolvla-closed-loop-acceptance.json`, and `reports/simulation/harness-live-eeg-smolvla-g1.json`. Reports are generated artifacts and are intentionally not treated as portable physical-hardware evidence.

本地权威产物为 `reports/training/smolvla-g1-suite-heldout.json`、`reports/simulation/g1-smolvla-closed-loop-acceptance.json` 和 `reports/simulation/harness-live-eeg-smolvla-g1.json`。这些报告属于生成产物，不能当作可迁移到真机的证据。

## Public EEG decoding / 公开 EEG 解析

`simulation/run_public_ssvep.sh` reads PhysioNet MAMEM experiment 3 through WFDB and keeps subjects 001/002 for training, 003 for threshold calibration, and 004 for testing. The primary decoder is Filter-Bank CCA; single-band CCA and the spectral MLP remain comparison baselines. Acceptance uses all held-out windows in recorded order and never depends on the selected-example Harness smoke test. Because experiment 3 contains only active SSVEP trials, its incorrect-event rate is not an idle false-activation rate.

`simulation/run_public_ssvep.sh` 通过 WFDB 读取 PhysioNet MAMEM Experiment 3，并固定使用受试者 001/002 训练、003 校准阈值、004 测试。主解析器为 Filter-Bank CCA；单频带 CCA 和 Spectral MLP 仅作为对照。验收使用全部留出窗口的原始顺序，不依赖挑选样本的 Harness 冒烟测试。由于 Experiment 3 只有主动 SSVEP Trial，其错误事件率不等同于 Idle 状态下的误触发率。

`simulation/run_public_ssvep_256.sh` is a separate high-density experiment using MAMEM experiment 2. It reads the official 256-channel, 250 Hz WFDB records, selects the named posterior channels `P7/O1/Oz/O2/P8`, uses two-second windows, and extracts Idle windows from the protocol-defined five-second rest intervals. The minimal four-subject run is intentionally strict: subjects 001/002 are development references, 003 calibrates the operating threshold, and 004 remains held out. The first verified run did not pass: held-out raw accuracy was 40%, and no calibration threshold preserved both useful coverage and Idle rejection. This is evidence that channel count alone does not solve cross-subject variability, not an accepted decoder.

`simulation/run_public_ssvep_256.sh` 是独立的高密度实验，使用 MAMEM Experiment 2。它通过 WFDB 读取官方 256 通道、250Hz 记录，选择明确命名的后脑区通道 `P7/O1/Oz/O2/P8`，采用 2 秒窗口，并从协议定义的 5 秒 Rest 区间提取 Idle。最小四受试者实验保持严格划分：001/002 仅作开发参考，003 校准工作阈值，004 完全留出。首次真实运行未通过：留出集原始准确率为 40%，不存在同时保留有效 Coverage 和 Idle 抑制的校准阈值。这证明增加通道数本身不能消除跨受试者差异，不能将其描述为已验收解析器。

## EEG-to-planner boundary / EEG 到规划器边界

`--eeg-planner-benchmark` consumes every event in an EEG report's `continuous_stream`. Only a decoded `select` may invoke the Planner; the benchmark never confirms or executes the generated plan. It reports selection precision, recall and F1, false Planner invocations per minute, conditional plan validity, end-to-end plan recall, unexpected executions, and EEG-window-plus-Planner P95 latency. With no Planner endpoint it uses `MockPlanner` to isolate the interface. Supplying `--planner-base-url`, `--planner-model`, and optionally `--planner-provider-name` measures the same boundary with a live OpenAI-compatible model.

`--eeg-planner-benchmark` 会消费 EEG 报告 `continuous_stream` 中的全部事件。只有解析出的 `select` 可以调用 Planner；该实验不会确认或执行生成的计划。报告包含 Select Precision、Recall、F1、每分钟错误 Planner 调用、条件计划有效率、端到端 Plan Recall、非预期执行次数，以及 EEG 窗口加 Planner 的 P95 延迟。不提供 Planner Endpoint 时使用 `MockPlanner` 隔离接口；提供 `--planner-base-url`、`--planner-model` 和可选的 `--planner-provider-name` 后，会用真实 OpenAI-compatible 模型测量同一边界。
