# Current Challenges and Next Decisions / 当前困难与下一步决策

## 2026-08-30 current priority / 2026-08-30 当前优先级

The active engineering target is now the VLA execution boundary. LeRobot is a committed lower-level dependency for policy, processor, dataset, robot, and inference interfaces. Synapse2Action remains the upper orchestration and governance layer that connects human intent, an LLM planner, confirmation, VLA execution, whole-body control, measured verification, recovery, and audit. It is not a competing training framework.

当前首要工程目标已经收敛为 VLA 执行边界。LeRobot 是 Policy、Processor、Dataset、Robot 与推理接口的确定依赖；Synapse2Action 保持为上层编排与治理层，负责串联人类意图、LLM Planner、确认、VLA 执行、全身控制、实测验收、恢复和审计，而不是与 LeRobot 竞争的训练框架。

The accepted GR00T path currently runs:

```text
human or scripted intent
→ Harness state machine
→ Mock or OpenAI-compatible planner
→ validated TaskSpec and confirmation
→ GR00T N1.6 G1 policy
→ official whole-body control
→ MuJoCo G1
→ independent physical evidence
```

当前已经验收的 GR00T 链路为：人类或脚本意图经过 Harness 状态机，由 Mock 或 OpenAI-compatible Planner 生成计划，经 TaskSpec 校验和人工确认后进入 GR00T N1.6 G1 Policy、官方全身控制与 MuJoCo G1，最后由独立物理证据判定结果。

### Current measured evidence / 当前实测证据

- The RTX 4070 runs the public G1 apple-to-plate checkpoint with approximately 10.4 GB VRAM use. A complete evidence-preserving rollout takes roughly three minutes; sampled GPU utilization was low, so serial simulation, WBC stepping, and policy IPC are more important throughput limits than raw GPU compute.
- The fixed-seed suite now contains 20 consecutive runs, seeds 1001–1020. Strict all-stage success was 1/20 (5%, Wilson 95% CI 0.9%–23.6%); only seed 1002 passed every measured stage.
- Stage rates were 85% contact, 75% grasp, 5% lift above 0.10 m, 40% plate contact/release/stable placement, and 100% standing. Mean maximum lift was only 0.0384 m.
- The primary measured bottleneck is therefore effective post-grasp lift and transport, not balance or infrastructure stability. A successful replay proves path reachability, not representative task performance.

- RTX 4070 可运行公开 G1 苹果放盘 checkpoint，显存约占 10.4GB。保留完整证据的单轮约需三分钟；抽样 GPU 利用率较低，当前吞吐瓶颈主要是串行仿真、WBC Step 和 Policy IPC，而非单纯 GPU 算力。
- 固定 Seed 1001–1020 的 20 次连续评测已完成。严格全阶段成功率为 1/20（5%，Wilson 95% CI 0.9%–23.6%）；仅 Seed 1002 通过全部实测阶段。
- 分阶段成功率为：接触 85%、抓取 75%、抬升超过 0.10m 为 5%、接触盘子/释放/稳定放置均为 40%、全程站立为 100%。平均最大抬升仅 0.0384m。
- 因此当前首要瓶颈不是平衡层或基础设施稳定性，而是抓取后的有效抬升与运输。成功回放只能证明链路可达，不能代表总体任务效果。

### Active problems / 当前问题

1. **VLA maturity and coverage.** The public checkpoint is task- and embodiment-specific. Failures vary by seed, and the system has not demonstrated generalization across objects, destinations, camera perturbations, or tasks. Model size alone is not the primary diagnosis; data coverage, long-horizon closed-loop behavior, and recovery examples are more direct gaps.
2. **No controlled recovery loop.** The current pipeline is one confirmed execution followed by verification. Evidence does not yet feed a bounded recovery plan back through the LLM and a second confirmation.
3. **Result semantics are conflated.** `outcome_success`, `process_compliance`, and `safety_passed` must be independent. A useful final placement must not be hidden by an unnecessary intermediate threshold, while safety invariants must remain non-negotiable.
4. **LeRobot boundary is incomplete.** The current GR00T/WBC runner directly manages vendor environments and JSON handoff. Standard policy, processor, dataset, and robot operations should move behind LeRobot; humanoid-specific WBC remains an explicit adapter boundary.
5. **Benchmark throughput and telemetry.** The 20-seed baseline is complete, but serial episodes remain slow and provide no intra-episode heartbeat. A resident policy server, optional video, parallel environments, smoke/full profiles, and stage progress telemetry are required.
6. **Only one mature checkpoint is qualified.** The architecture claim requires a second LeRobot-supported policy under identical TaskSpec, seeds, and evidence gates.
7. **Simulation is not hardware evidence.** Camera calibration, latency, joint mapping, payload behavior, physical emergency stop, workspace enforcement, and operator takeover remain unverified on a real G1.
8. **Python runtime split.** The main Harness uses Python 3.12 while the compatible WBC runtime uses Python 3.10. The boundary must remain a versioned data contract; importing the main package inside the vendor runtime is not supported.
9. **Language-to-work causality is unproven.** One TaskSpec cannot establish that language controls behavior across paraphrases, changed goals, forbidden objects, and impossible requests.
10. **The production gap is not a model-size problem.** Reliability, failure detection, deterministic safety, recovery, cycle time, intervention rate, embodiment transfer, and versioned requalification remain unresolved even with a stronger VLA.

1. **VLA 成熟度与覆盖不足。** 公开 checkpoint 绑定特定任务和本体，不同 Seed 结果波动，尚未证明跨物体、目标、相机扰动和任务的泛化。问题不能简单归因于模型参数较小；数据覆盖、长时序闭环和恢复示范是更直接的缺口。
2. **尚无受控恢复循环。** 当前管线是确认后执行一次，再进行验收；失败证据尚未经过 LLM 生成有界恢复计划、再次确认并重试。
3. **结果语义仍混杂。** 必须独立报告 `outcome_success`、`process_compliance` 和 `safety_passed`。不必要的中间阈值不能掩盖有价值的最终结果，而安全不变量必须保持强制。
4. **LeRobot 边界尚未收敛。** 当前 GR00T/WBC runner 仍直接管理 Vendor 环境与 JSON 交接；标准 Policy、Processor、Dataset 和 Robot 操作应迁移到 LeRobot，人形 WBC 保持为显式专用 Adapter 边界。
5. **评测吞吐与遥测不足。** 20 个 Seed 的基线已完成，但串行 Episode 仍然缓慢，且单次运行内部没有心跳；需要常驻 Policy Server、可选视频、并行环境、Smoke/Full 两级评测和阶段进度遥测。
6. **只验收了一个成熟 checkpoint。** 架构主张需要第二个 LeRobot 支持的 Policy 在相同 TaskSpec、Seed 和证据门下完成对照。
7. **仿真不是真机证据。** 真机相机标定、延迟、关节映射、负载、实体急停、工作空间约束和人工接管均未验证。
8. **Python Runtime 分裂。** 主 Harness 使用 Python 3.12，兼容 WBC Runtime 使用 Python 3.10；边界必须保持为版本化数据契约，不支持 Vendor Runtime 直接 Import 主包。
9. **尚未证明语言到工作的因果性。** 单一 TaskSpec 无法证明语言能够跨同义改写、目标变化、禁止物体和不可能请求稳定控制行为。
10. **工业化差距不是模型大小问题。** 即使换成更强 VLA，可靠性、失败检测、确定性安全、恢复、节拍、人工介入率、本体迁移和版本化重新验收仍未解决。

### Immediate roadmap / 近期路线

1. Version the result schema with separate outcome, process, and safety decisions.
2. Use the completed 20-seed baseline to isolate lift failures with controlled action, contact, timing, and scene counterfactuals.
3. Move standard policy operations behind LeRobot and introduce OpenPI only as a non-authoritative research backend.
4. Qualify a second mature policy under the same TaskSpec, seeds, and verifier.
5. Add at least three independent TaskSpecs and prove paraphrase invariance, counterfactual sensitivity, refusal, and constraint binding.
6. Add bounded recovery only after failure classes and allowed recovery skills are explicit.
7. Begin physical-G1 work only with read-only preflight, physical emergency stop, supervised workspace, and operator takeover.

1. 升级结果 Schema，分别输出结果、过程与安全判定。
2. 基于已完成的 20-Seed 基线，用受控动作、接触、时序与场景反事实定位抬升失败原因。
3. 将标准 Policy 操作迁移到 LeRobot，并仅把 OpenPI 作为不拥有最终控制权的研究 Backend。
4. 让第二个成熟 Policy 在相同 TaskSpec、Seed 和 Verifier 下完成验收。
5. 增加至少三个独立 TaskSpec，并证明同义改写不变性、反事实敏感性、拒绝能力与约束绑定。
6. 仅在失败分类和允许的恢复技能明确后，增加有界恢复。
7. 只有在只读预检、实体急停、受控工作区和人工接管就绪后，才开始 G1 真机工作。

The full engineering and industrialization rationale is maintained in [Language-to-Work Industrialization Gap](industrialization-gap.md).

完整工程与工业化依据见[语言到工作工业化差距](industrialization-gap.md)。

The sections below preserve the earlier SmolVLA and controller findings as historical evidence. They no longer describe the active implementation priority.

以下章节保留早期 SmolVLA 与 Controller 结论作为历史证据，但不再代表当前实现优先级。

## Historical SmolVLA checkpoint / 历史 SmolVLA 检查点

Synapse2Action has demonstrated that public EEG replay, a real LLM planner, real SmolVLA inference, the Harness, Unitree SDK2, and MuJoCo can execute in one pipeline. That result proves component connectivity, but it does not yet prove a stable human-to-robot system.

Synapse2Action 已经证明公开 EEG 回放、真实 LLM Planner、真实 SmolVLA 推理、Harness、Unitree SDK2 和 MuJoCo 可以在同一条链路中运行。这证明了组件可以连接，但还没有证明系统已经形成稳定的人机闭环。

Further feature work is paused because the remaining failures are architectural. Adding more UI states, model providers, scenarios, or tuning constants would increase surface area without resolving the control problem.

当前暂停继续堆叠功能，因为剩余失败属于架构问题。继续增加 UI 状态、模型 Provider、实验场景或调节常数，只会扩大系统表面积，不会解决控制问题。

## What is verified / 已验证的部分

- The Harness now follows `select → plan → review → confirm → execute → verify`. Confirmation applies to a concrete validated plan rather than an unknown future plan.
- SmolVLA produces real 29-DoF action chunks. A bounded projector can give those chunks a measurable, non-zero contribution at the SDK2 command boundary.
- The official SDK2 message path, MuJoCo bridge, and Unitree lower-body RL controller run together.
- Independent checks can reject a run for falling, missing the grasp, insufficient lift, failed release, or placement outside the tray.
- The full software test suite passes, and failed physical rollouts are preserved instead of being rewritten as successes.

- Harness 已调整为 `选择 → 规划 → 审阅 → 确认 → 执行 → 验证`，确认针对已经生成并校验的具体计划。
- SmolVLA 会真实生成 29-DoF Action Chunk，受限投影器能够让这些输出在 SDK2 命令边界产生可测量的非零贡献。
- 官方 SDK2 消息链、MuJoCo Bridge 和宇树下肢 RL Controller 可以共同运行。
- 独立验收会因跌倒、未抓住、抬升不足、释放失败或未落入托盘而拒绝实验。
- 完整软件测试通过，物理仿真失败会被保留，不会被改写成成功。

## The current failure / 当前失败

Repeated SmolVLA + SDK2 + MuJoCo rollouts do not yet meet a stability gate. Recent three-run evaluations produced approximately one accepted run out of three. Different rejected runs showed:

- the object was grasped and released but was not lifted by the required 0.10 m;
- the object was transported far outside the tray;
- the manipulation succeeded but the robot fell during or after transport;
- the base height dropped to approximately 0.12–0.15 m in severe failures;
- an otherwise identical run occasionally missed the grasp.

重复运行 SmolVLA + SDK2 + MuJoCo 后，系统仍未通过稳定性门槛。近期三次一组的实验大约只有一次通过。不同失败包括：

- 已抓取并释放，但抬升高度没有达到 0.10m；
- 物体被搬运到托盘之外很远的位置；
- 抓放完成，但机器人在运输阶段或运输后跌倒；
- 严重失败时基座高度下降到约 0.12–0.15m；
- 相同配置偶尔无法完成抓取。

These failures remain real even when VLA residuals are reduced to very small values. Attempts to scale residuals by phase, freeze VLA after grasp, synchronize against MuJoCo time, slow the trajectory, and advance phases from measured events did not produce repeatable acceptance. Those experimental changes were therefore not committed.

即使把 VLA 残差缩小到很低，上述失败仍然存在。我们尝试过按阶段缩放残差、抓取后冻结 VLA、使用 MuJoCo 时间同步、放慢轨迹以及依据物理事件推进阶段，但都没有获得可重复的通过结果。因此这些实验性改动没有提交。

## Root architectural conflict / 根本架构矛盾

The current controller is primarily a lower-body locomotion policy. The manipulation path independently moves the waist and both arms while the robot may carry an object. The balance policy was not demonstrated to have been trained with these upper-body motions, payload changes, and center-of-mass disturbances.

当前 Controller 本质上是下肢 locomotion policy。操作轨迹会独立改变腰部和双臂，并可能携带物体；现有平衡策略没有证据表明它针对这些上肢动作、负载变化和质心扰动进行过训练。

This creates an unstable composition:

```text
lower-body RL balance policy
+ independently generated upper-body trajectory
+ VLA residual action
+ attached object payload
= no proven whole-body stability guarantee
```

The failure cannot be responsibly fixed by selecting a nicer residual weight or retrying until one rollout passes. The system needs a controller whose training objective and observations include the manipulation task.

这个问题不能靠选择一个更好看的残差比例，或者反复运行直到偶然成功来解决。系统需要一个在训练目标和观测中真正包含操作任务的 Controller。

## Other unresolved product questions / 其他尚未解决的产品问题

### EEG meaning / EEG 的真实含义

The public SSVEP dataset proves decoding and replay, but it does not prove that a person selected a visible object in the MuJoCo scene. A future experiment must bind visual stimuli, scene object IDs, EEG windows, confidence, and confirmation to the same timestamped session.

公开 SSVEP 数据证明了解码和回放，但没有证明真人在 MuJoCo 场景中选择了某个可见物体。未来实验必须把视觉刺激、场景 Object ID、EEG 时间窗、置信度和确认绑定到同一个带时间戳会话。

The current subject-independent MAMEM experiment uses Filter-Bank CCA. On subject 004 it reaches 82.5% raw accuracy and 92.6% accepted accuracy at 67.5% coverage. All 40 test windows are also evaluated in recorded order: 25 of 27 accepted events are correct, or 0.6 accepted misclassifications per minute. The decision latency is still five seconds, and this dataset has no idle class, so it cannot measure idle false activations. The selected-example Harness replay is retained only as an interface smoke test and is not execution evidence.

当前跨受试者 MAMEM 实验使用 Filter-Bank CCA。在受试者 004 上，原始准确率为 82.5%，67.5% Coverage 下的接受后准确率为 92.6%。全部 40 个测试窗口还会按记录顺序评估：27 次接受事件中 25 次正确，即每分钟 0.6 次接受后误分类。决策延迟仍为 5 秒，而且该数据集没有 Idle 类，因此无法测量空闲误触发。挑选正确样本的 Harness 回放仅保留为接口冒烟测试，不再作为执行证据。

The first 256-channel MAMEM experiment-2 run adds protocol-defined Rest and two-second windows but fails its release gate. Subject-level FBCCA accuracy varies from 40% to 85%; held-out subject 004 reaches only 40%, and an Idle-safe calibration threshold abstains on every test window. The next valid experiment therefore needs same-person multi-session calibration and a later-session holdout. Selecting channels or thresholds from subject 004 would leak the test set.

首轮 256 通道 MAMEM Experiment 2 已加入协议定义的 Rest 和 2 秒窗口，但未通过发布门。不同受试者的 FBCCA 准确率在 40% 至 85% 之间；留出受试者 004 只有 40%，满足 Idle 安全要求的校准阈值会在全部测试窗口上弃权。所以下一个有效实验必须采用同一受试者多 Session 校准、后续 Session 留出的设计；根据受试者 004 选择通道或阈值会造成测试集泄漏。

### LLM value / LLM 的必要性

For a fixed `red_cube → drop_tray` task, an LLM adds little beyond a deterministic skill lookup. The project must decide whether the research question is complex task planning, brain-authorized autonomy, or VLA control. Otherwise every model is present, but no model has a necessary role.

对于固定的 `red_cube → drop_tray`，LLM 相比确定性技能查询没有体现明显必要性。项目必须决定研究问题究竟是复杂任务规划、脑意图授权自主执行，还是 VLA 控制；否则所有模型都出现了，但没有模型承担不可替代的职责。

The structured Planner action now crosses the subprocess boundary and is recorded as the VLA task binding. Task semantics are no longer compiled into the Planner, simulator, controller, verifier, or dashboard; they share one `TaskSpec`. The latest TaskSpec-driven real run received three chunks with a 10.31-second first-chunk latency inside 16.67 seconds of coverage, zero stale fallbacks, and passed standing, grasp, lift, release, and placement. Under the same observation and seed, changing the language plan previously produced a 0.02262-rad RMS action difference across a 50-frame, 29-dimensional chunk. This validates transport and language conditioning, not that an LLM is necessary for the single configured task; the accepted binding run used `MockPlanner`, so a live-LLM repetition and multiple independent TaskSpecs remain required before making a production-LLM or task-generalization claim.

现在结构化 Planner Action 已跨越子进程边界，并作为 VLA Task Binding 写入报告；Planner、模拟器、Controller、Verifier 和 Dashboard 不再各自编译任务语义，而是共享一个 `TaskSpec`。最新 TaskSpec 驱动的真实运行收到 3 个 Chunk，首 Chunk 延迟 10.31 秒，低于 16.67 秒覆盖窗口，且无 Stale Fallback，并通过站立、抓取、抬升、释放和落盘验收。此前在观测和随机种子完全相同的条件下，更换语言 Plan 后，50 帧、29 维 Action Chunk 的 RMS 差异为 0.02262rad。这证明了数据传递和语言条件作用，但尚未证明单个配置任务必须使用 LLM；当前通过绑定验收的运行使用 `MockPlanner`，在声称真实生产 LLM或任务泛化前，仍需用 Live LLM 和多个独立 TaskSpec 重复实验。

### VLA claim / VLA 能力口径

The current VLA contribution is deliberately bounded. That is appropriate for safety research, but a non-zero joint delta alone does not prove that VLA improves task performance. Future evaluation must compare VLA-on and VLA-off rollouts under controlled visual perturbations.

当前 VLA 贡献被刻意限制，这符合安全研究需要；但“关节变化非零”本身不能证明 VLA 改善了任务表现。未来必须在受控视觉扰动下比较 VLA 开启与关闭的闭环结果。

### Simulation-to-hardware gap / 仿真到真机的距离

No result currently establishes physical G1 safety, network timing, joint mapping, camera calibration, payload behavior, emergency stop, or operator takeover. MuJoCo acceptance is not portable physical evidence.

当前没有任何结果能够证明 G1 真机安全、网络时序、关节映射、相机标定、负载行为、实体急停或人工接管。MuJoCo 验收不能直接作为真机证据。

## Decisions required before more implementation / 继续实现前必须作出的决策

### 1. Fix the primary engineering claim / 固定首要工程命题

The project-level claim is now fixed: reconstruct the functional path from biological intent through synthetic cognition and an artificial spinal system to embodied action. The next milestone must still select one interface of that path as its primary engineering target:

1. EEG reliably selects and confirms robot tasks.
2. An LLM safely plans multi-step tasks behind the Harness.
3. A VLA policy improves manipulation under visual variation.
4. A whole-body controller stably executes manipulation on G1.

项目级命题已经明确：重建从生物意图、人工认知、人工脊髓到具身行动的功能链路。下一阶段仍必须只选择其中一个接口作为首要工程目标；四条同时推进会让每一层都停留在演示状态。

### 2. Choose the control architecture / 选择控制架构

Before more rollout tuning, decide between:

- a whole-body RL policy trained with waist, arm, payload, and balance objectives;
- a whole-body model-predictive controller with VLA-generated task-space targets;
- a stationary manipulation mode with explicit stance locking and arm-only control;
- a simpler robot or tabletop arm for validating EEG/LLM/VLA before returning to G1 balance.

在继续调整 rollout 前，需要在 whole-body RL、全身 MPC、固定站姿操作模式，或先使用桌面机械臂验证上层链路之间做出选择。

### 3. Define evidence gates / 定义证据门槛

Single successful runs are no longer sufficient. The next controller must pass a versioned repeated-run gate, for example:

- at least 20 seeded or timing-varied rollouts;
- at least 90% full task success;
- 100% remained standing and finite;
- zero unbounded or stale actions;
- separately reported grasp, lift, transport, release, and placement rates;
- VLA-on versus VLA-off comparison using the same scenarios.

单次成功不再构成验收。下一版 Controller 应通过版本化重复实验门槛，例如至少 20 次不同 seed 或时序的 rollout、完整任务成功率不低于 90%、站立和数值有限性为 100%，并分别报告各阶段成功率以及 VLA 开关对照。

## Recommended next step / 建议的下一步

Do not add another model or frontend feature yet. First write a one-page experiment thesis that selects the primary claim, then choose the matching control architecture. If G1 whole-body manipulation remains the target, the next implementation should be a reproducible controller-training and repeated-rollout evaluation project, not another end-to-end demo run.

暂时不要继续增加模型或前端功能。先用一页纸确定首要研究命题，再选择与之匹配的控制架构。如果目标仍然是 G1 全身操作，那么下一项实现应该是可复现的 Controller 训练与重复 rollout 评测，而不是再运行一次端到端演示。
