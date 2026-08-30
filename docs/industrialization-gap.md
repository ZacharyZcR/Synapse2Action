# Language-to-Work Industrialization Gap / 语言到工作工业化差距

## Objective / 目标

The product vision is not merely to make a robot move after receiving text. It is to convert a human instruction into a bounded, reviewable, executable, verifiable, and recoverable physical job:

产品目标不只是让机器人收到文本后产生动作，而是把人的指令转换成有边界、可审阅、可执行、可验证、可恢复的物理工作：

```text
language intent
→ grounded TaskSpec
→ validated plan and authorization
→ VLA action proposal
→ deterministic safety projection
→ whole-body control
→ measured physical outcome
→ bounded recovery or safe stop
```

OpenPI, GR00T, and SmolVLA address important portions of action generation. None of them, by itself, supplies the complete production runtime above. Synapse2Action owns the missing orchestration, authority, evidence, and recovery semantics rather than training another foundation model from scratch.

OpenPI、GR00T 与 SmolVLA 解决了动作生成的重要部分，但任何一个都不能单独提供上述完整生产 Runtime。Synapse2Action 的职责是补齐编排、权限、证据与恢复语义，而不是从零训练另一个基础模型。

## Current measured reality / 当前实测现实

The accepted GR00T N1.6 path proves connectivity and measurable physical progress in MuJoCo, not reliable work completion. On the fixed seeds 1001–1020:

已验收的 GR00T N1.6 链路证明了 MuJoCo 中的连通性与可测物理进展，但尚未证明可靠完成工作。固定 Seed 1001–1020 的结果为：

| Gate | Result |
|---|---:|
| Strict all-stage success / 严格全阶段成功 | 1/20, 5% |
| Contact / 接触 | 85% |
| Grasp / 抓取 | 75% |
| Lift above 0.10 m / 抬升超过 0.10m | 5% |
| Plate contact, release, stable placement / 接触盘子、释放、稳定放置 | 40% each / 各 40% |
| Remained standing / 全程站立 | 100% |
| Mean maximum lift / 平均最大抬升 | 0.0384 m |

The primary failure is therefore post-grasp lift and transport, not basic balance, model loading, or Harness connectivity. One successful replay demonstrates reachability; it is not a reliability claim.

因此，当前首要失败位于抓取后的抬升与运输，不是基础平衡、模型加载或 Harness 连通性。一次成功回放只证明路径可达，不能作为可靠性结论。

## What remains difficult for OpenPI-class systems / OpenPI 这一代系统仍未解决的问题

### Embodiment and data coupling / 本体与数据耦合

A policy remains coupled to its cameras, gripper, action representation, controller frequency, calibration, and normalization. OpenPI explicitly recommends fine-tuning on the target robot, and its DROID checkpoints are not expected to work unchanged on a different physical setup. A low offline loss does not prove a successful closed-loop rollout.

Policy 仍然绑定相机、夹爪、动作表示、控制频率、标定与归一化。OpenPI 明确建议在目标机器人上微调；DROID checkpoint 也不预期在不同物理配置上原样工作。较低的离线 Loss 不能证明闭环成功。

### Language causality / 语言因果性

Accepting a prompt is not evidence that language caused the behavior. A policy may follow visual shortcuts, the initial pose, or task imbalance and ignore wording. Qualification therefore requires paraphrase invariance and counterfactual sensitivity under the same observation and seed.

模型接收 Prompt 不等于语言真正导致了行为。Policy 可能依赖视觉捷径、初始姿态或任务分布，而忽略措辞。因此验收必须在相同 Observation 与 Seed 下同时证明同义改写不改变目标、反事实指令会改变行为。

### Partial observability and memory / 部分可观测与记忆

Occlusion, leaving a room, opening a drawer, and moving an object all require persistent world state. The π0.5 paper reports failures involving occluded targets, unfamiliar fixtures, and repeated high-level subtasks. More parameters alone do not provide object permanence, calibrated memory, or completion accounting.

遮挡、离开房间、打开抽屉和移动物体都需要持续世界状态。π0.5 论文报告了目标被遮挡、陌生机构以及高层子任务重复等失败。单纯增加参数不能自动获得物体恒存、可信记忆或完成度核算。

### Contact-rich control / 接触丰富控制

Grasping, lifting, deformable objects, payload changes, and whole-body balance depend on dynamics that are poorly captured by images and joint positions alone. A VLA action chunk must remain a proposal; force, torque, velocity, collision, workspace, and balance enforcement belong to deterministic controllers.

抓取、抬升、柔性物体、负载变化与全身平衡依赖的动力学，无法只靠图像和关节位置充分表达。VLA Action Chunk 必须只是提案；力、力矩、速度、碰撞、工作空间和平衡约束属于确定性 Controller。

### Verification and recovery / 验证与恢复

The model cannot be trusted to declare success. Robot state, object state, vision, contact, and force evidence must determine the result. A failed stage needs an explicit failure class and a small allowlist of recovery skills; unconstrained LLM replanning is not recovery.

不能相信模型自报成功。结果必须由机器人状态、物体状态、视觉、接触与力证据决定。失败阶段需要明确的失败分类和小规模恢复技能白名单；无限制 LLM 重规划不等于恢复。

## Why general language-driven robots are not yet ordinary production equipment / 为什么通用语言机器人尚未成为普通生产设备

1. **Reliability compounds across steps.** Ten stages at 95% reliability yield only about 60% end-to-end success. Research-level success rates are economically unacceptable at production volume.
2. **Failures are not yet bounded.** A production cell needs predictable safe states, deterministic stop paths, and diagnosable fault classes, not merely a higher mean score.
3. **Distribution shift is cheap to create.** Camera motion, lighting, packaging, tool wear, payload, and software updates can change behavior and force requalification.
4. **Validation can cost more than training.** Every robot, tool, task, and model update needs repeated physical trials, evidence retention, and regression analysis.
5. **Cycle time and intervention dominate ROI.** A visually impressive policy that needs frequent operator rescue may be worse than a narrow PLC/vision system.
6. **Safety certification covers the robot application and cell.** ISO 10218-1:2025 and ISO 10218-2:2025 address industrial robots and robot applications/cells; a generative model cannot replace the required deterministic safety architecture.
7. **Responsibility must remain legible.** Operations teams need to know whether perception, planning, policy, controller, hardware, or verification failed and which version produced the behavior.

1. **多步骤可靠性会相乘。** 十个阶段即使各有 95% 可靠性，端到端也只有约 60%；研究级成功率在生产规模下不可接受。
2. **失败边界尚不清楚。** 生产单元需要可预测安全状态、确定停止路径和可诊断故障类别，而不只是更高平均分。
3. **分布漂移很容易发生。** 相机移动、光照、包装、工具磨损、负载和软件升级都可能改变行为，并触发重新验收。
4. **验证成本可能高于训练。** 每种机器人、工具、任务与模型更新都需要重复真机试验、证据保留和回归分析。
5. **节拍与人工介入决定 ROI。** 经常需要人工救援的漂亮 Policy，可能不如能力窄但稳定的 PLC/传统视觉系统。
6. **安全认证覆盖整个机器人应用和工作单元。** ISO 10218-1:2025 与 ISO 10218-2:2025 分别覆盖工业机器人及其应用/Cell；生成模型不能取代确定性安全架构。
7. **责任链必须可读。** 运维需要知道是感知、规划、Policy、Controller、硬件还是验证失败，以及哪个版本产生了该行为。

## Product architecture boundary / 产品架构边界

```text
Human language
→ LLM Planner: structured intent and candidate skills
→ Harness: schema, context, risk, review, confirmation
→ OpenPI / GR00T / SmolVLA: untrusted action proposal
→ Safety Supervisor: finite, stale, workspace, velocity, collision checks
→ Whole-Body Controller: balance and physical execution
→ Robot
→ Independent Verifier
→ complete | bounded recovery | safe stop
```

The LLM and VLA never own emergency stop, collision enforcement, torque limits, workspace limits, or the final success verdict.

LLM 与 VLA 永远不拥有急停、碰撞约束、力矩限制、工作空间限制和最终成功判定权。

## Active delivery plan / 当前交付路线

### Milestone A — Explain and fix the measured lift failure / 解释并修复实测抬升失败

- [x] Version the result schema into `outcome_success`, `process_compliance`, and `safety_passed`.
- [x] Add a reproducible same-seed counterfactual harness for action horizon and episode budget, with paired effect aggregation.
- [ ] Run seeds 1001–1020 on the GR00T host; add grasp/contact and scene interventions only through validated physical environment controls.
- [ ] Determine whether the failure belongs to policy output, action decoding, controller tracking, contact dynamics, or verifier semantics.
- [ ] Preserve the original 20-seed baseline; do not tune on the held-out acceptance set.

### Milestone B — Standard policy boundary and second policy / 标准 Policy 边界与第二个 Policy

- [ ] Move standard processor, normalization, policy-server, and action-chunk operations behind a LeRobot-backed adapter contract.
- [x] Unify SmolVLA and OpenPI proposals behind the bounded Action Chunk client contract.
- [x] Add a tested OpenPI research adapter that requires explicit observation encoding and embodiment mapping without bypassing the Harness, safety supervisor, WBC, or verifier.
- [ ] First qualify the adapter on a supported tabletop/simulation embodiment; do not claim a G1 checkpoint where none exists.
- [ ] Evaluate a second mature policy under the same TaskSpec, seeds, and evidence schema.

### Milestone C — Prove language-to-work causality / 证明语言到工作的因果链

- [x] Define three independent TaskSpecs with different targets, destinations, and physical success conditions.
- [x] Version a qualification manifest for paraphrases, counterfactuals, forbidden-object constraints, and impossible requests.
- [ ] Execute the qualification manifest against each candidate policy under matched observations and seeds.
- [ ] Require the structured plan to cross the exact Planner-to-VLA boundary recorded in evidence.
- [x] Add a fail-closed Policy Admission Verifier that binds language evidence to the manifest hash and jointly checks exact seeds, Result v3, authorization traces, recovery limits, safety, process compliance, and outcome rate.
- [x] Freeze admitted inputs, release identities, and hashes into non-overwriting evidence bundles; reject tampering, undeclared files, lowered thresholds, and reduced baseline seeds.
- [x] Classify outcome, process, and safety failures and emit a deterministic recovery allowlist; safety violations permit no retry.
- [x] Route an allowlisted recovery plan through fresh world validation, a new authorization challenge, and a second explicit confirmation before executing at most one attempt.
- [ ] Qualify recovery success and failure-detection recall with real candidate policies; the current acceptance is hardware-free state-machine evidence.

### Milestone D — Physical G1 preflight / G1 真机预检

- [ ] Validate network, DDS domain, clocks, cameras, joint mapping, and command rate without actuation.
- [ ] Require a physical emergency stop, supervised workspace, operator takeover, and written preflight checklist.
- [ ] Progress through read-only state, replay, single-joint, scripted skill, VLA skill, and language authorization gates.
- [ ] Compare simulation and physical traces before increasing authority.

### Production qualification metrics / 生产准入指标

Research success rate alone is insufficient. Every release candidate must also report task-time distribution, interventions per operating hour, failure-detection recall, safe-stop latency, recovery success, continuous run duration, hardware faults, and regression by model/data/controller version.

The admission verifier and evidence-bundle verifier are evidence gates, not evidence generation. No policy is accepted until real candidate runs and the matched language evaluation are supplied; the current GR00T 1/20 strict result does not satisfy a production reliability threshold. A bundle digest is not a signature: its trusted value must be retained externally or signed before it can defend against an adversary who can rewrite the whole bundle.

仅报告研究成功率不够。每个发布候选还必须报告任务耗时分布、每运行小时人工介入次数、失败检测召回率、安全停止延迟、恢复成功率、连续运行时长、硬件故障，以及按模型、数据、Controller 版本划分的回归结果。

## Primary external evidence / 主要外部依据

- [OpenPI repository and deployment boundary](https://github.com/Physical-Intelligence/openpi)
- [π0.5 paper and stated limitations](https://www.physicalintelligence.company/download/pi05.pdf)
- [RoboArena real-world policy evaluation](https://proceedings.mlr.press/v305/atreya25a.html)
- [ISO robotics standards catalogue](https://www.iso.org/committee/5915511/x/catalogue/)

External results remain upstream claims until reproduced under this repository's TaskSpec, seeds, adapters, and verifier.

外部结果在通过本仓库的 TaskSpec、Seed、Adapter 与 Verifier 复现前，始终属于上游结论。
