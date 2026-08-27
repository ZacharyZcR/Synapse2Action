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
