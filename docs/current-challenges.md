# Current Challenges and Next Decisions / 当前困难与下一步决策

## Why development is paused here / 为什么在这里暂停推进

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

### LLM value / LLM 的必要性

For a fixed `red_cube → drop_tray` task, an LLM adds little beyond a deterministic skill lookup. The project must decide whether the research question is complex task planning, brain-authorized autonomy, or VLA control. Otherwise every model is present, but no model has a necessary role.

对于固定的 `red_cube → drop_tray`，LLM 相比确定性技能查询没有体现明显必要性。项目必须决定研究问题究竟是复杂任务规划、脑意图授权自主执行，还是 VLA 控制；否则所有模型都出现了，但没有模型承担不可替代的职责。

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
