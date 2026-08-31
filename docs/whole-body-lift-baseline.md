# OpenWBT/OpenTrack Lift Baseline / 全身抬升基线

This experiment asks one narrow question: can an OpenWBT-style whole-body skill or an OpenTrack specialist execute post-grasp lift more reliably than the current GR00T baseline under matched G1 simulation conditions?

本实验只回答一个问题：在匹配的 G1 仿真条件下，OpenWBT 风格全身技能或 OpenTrack Specialist 能否比当前 GR00T 基线更可靠地完成抓取后抬升。

## Evidence boundary / 证据边界

The repositories are pinned in `simulation/whole_body.lock.json`. Staging source code, importing a module, replaying an upstream video, or tracking a motion without an object does not count as a Synapse2Action lift result. OpenWBT is a teleoperation/control reference; OpenTrack is a motion tracker. Neither is a language-conditioned manipulation policy.

两个仓库固定在 `simulation/whole_body.lock.json`。仅拉取源码、成功 Import、播放上游视频，或无物体动作跟踪均不计为 Synapse2Action 抬升结果。OpenWBT 是遥操作与控制参考，OpenTrack 是动作跟踪器；二者都不是语言条件操作 Policy。

## Matched protocol / 匹配协议

1. Use the same G1 embodiment, object, initial object pose, grasp state, control rate, simulation duration, and seeds as the retained GR00T suite.
2. Begin from a verifier-confirmed grasp so the experiment isolates post-grasp control rather than perception or grasp acquisition.
3. Compare three candidates: retained GR00T rollout, an OpenWBT teleoperated/reference lift, and an OpenTrack `lift_with_payload` specialist when trained.
4. Preserve raw joint state, object pose, contact state, controller state, commanded action, torque clipping, fall state, and stop reason.
5. Feed results through the existing Result v3 and Policy Admission evidence path. Upstream success claims are not accepted evidence.

1. 使用与现有 GR00T 证据相同的 G1 本体、物体、初始位姿、抓取状态、控制频率、仿真时长和 Seed。
2. 从 Verifier 已确认的稳定抓取状态开始，以隔离抓取后的控制问题。
3. 比较现有 GR00T、OpenWBT 遥操作/参考抬升，以及训练完成后的 OpenTrack `lift_with_payload` Specialist。
4. 保留关节状态、物体位姿、接触、Controller 状态、动作命令、Torque clipping、跌倒状态和停止原因。
5. 结果必须进入现有 Result v3 与 Policy Admission 证据链；不接受上游自报成功。

## Gates / 门槛

- Source/runtime readiness passes at the exact locked commits.
- At least 20 matched seeds are completed without selecting successful runs after the fact.
- Lift clearance above 0.10 m, grasp retention, standing, finite commands, and safety stops are reported separately.
- A candidate must exceed the retained 5% GR00T lift rate and ultimately meet the project admission threshold before routing can mark it `admitted`.
- Physical G1 deployment remains prohibited until simulation evidence, collision/workspace checks, physical emergency stop, and operator takeover are ready.

The first executable command on a compatible Linux host is:

```bash
./simulation/bootstrap_whole_body.sh
python3 simulation/check_whole_body_readiness.py
```

Passing readiness means only that exact source and deployment surfaces exist. It does not mean that dependencies, checkpoints, simulation, or physical execution have passed.
