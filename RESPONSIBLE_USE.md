# Responsible Use / 负责任使用

## Intended use / 预期用途

Synapse2Action is a research harness for bounded intent authorization, planning,
robot-policy evaluation, simulation, and supervised laboratory robotics. It is
not a medical device, assistive-control product, autonomous industrial safety
system, or permission to operate a physical robot.

Synapse2Action 是面向受限意图授权、规划、机器人 Policy 评测、仿真和受监督
实验室机器人的研究 Harness。它不是医疗器械、辅助控制产品、工业自主安全系统，
也不构成操作真机的许可。

## Prohibited use / 禁止用途

- Weapons, coercion, surveillance, policing, targeting, or harm to people.
- Unsupervised physical operation, public-space deployment, or bypassing an
  emergency stop, safety controller, workspace, collision, or torque limit.
- Inferring health, identity, emotion, intent, employability, or culpability
  from neural or behavioral data outside an approved research protocol.
- Executing hidden, ambiguous, stale, unconfirmed, or model-invented goals.
- Presenting simulation, replay, upstream claims, or selected successes as
  evidence of clinical, physical, general-purpose, or production reliability.

- 禁止用于武器、胁迫、监控、执法、目标选择或伤害人员。
- 禁止无人监督真机运行、公共空间部署，或绕过急停、安全 Controller、工作空间、
  碰撞和力矩限制。
- 禁止在获批研究协议外使用神经或行为数据推断健康、身份、情绪、意图、就业能力
  或责任。
- 禁止执行隐藏、含糊、过期、未确认或模型虚构的目标。
- 禁止将仿真、回放、上游声明或筛选后的成功样本表述为临床、真机、通用或生产
  可靠性证据。

## Required safeguards / 必需保护

Physical work requires a named operator, written task and workspace limits,
preflight, physical emergency stop, deterministic controller limits, independent
outcome verification, safe-stop behavior, retained audit evidence, and explicit
authorization for every execution and bounded recovery. Human override always
has priority over Planner, Policy, and recovery logic.

真机任务必须具备实名 Operator、书面任务和工作空间限制、Preflight、实体急停、
确定性 Controller 限制、独立结果验证、安全停止、审计证据，以及对每次执行和
受限恢复的明确授权。人工接管始终优先于 Planner、Policy 和恢复逻辑。

## Evidence language / 证据口径

Report what was measured, where, with which revision, and over how many trials.
Separate outcome success, process compliance, safety, abstention, intervention,
latency, recovery, and uncertainty. A component may be integrated without being
qualified, and a qualified simulation policy may still be unsafe on hardware.

报告必须说明测量内容、环境、Revision 和试验次数，并分别报告结果成功、过程
合规、安全、拒识、人工介入、延迟、恢复与不确定性。组件已集成不等于已验收；
仿真中通过验收的 Policy 仍可能不适用于真机。
