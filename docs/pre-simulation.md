# Pre-simulation readiness

This document defines the software boundary immediately before robot dynamics are introduced. It prevents deterministic substitutes, live providers, and simulators from being reported as the same kind of evidence.

The requirement-by-requirement status is recorded in [`pre-simulation-audit.md`](pre-simulation-audit.md); live-provider operation is described in [`live-planner-benchmark.md`](live-planner-benchmark.md).

## Ready now

| Layer | Concrete implementation | Evidence produced |
|---|---|---|
| Contracts | Versioned intent, world-state, plan, skill, action, and result schemas | `--contract-catalog` JSON |
| Intent | Scripted, keyboard, synthetic SSVEP, and recorded-window replay sources | decoded intents and state trace |
| Authorization | target/revision/time-bound, single-use challenge | confirmation/rejection trace |
| Planner boundary | mock, embedded HTTP, and external OpenAI-compatible adapter | request count, plan trace, local schema rejection |
| Planner robustness | eight deterministic valid, refusal, malformed, invented, unsafe, substituted, and timeout cases | `--planner-benchmark` report |
| Live planner evaluation | provider-neutral execute/refuse suite with local prompt-injection rejection | measured schema compliance, unsafe executions, errors, median and p95 latency |
| Policy | scripted tabletop policy and serialized VLA navigation policy | action steps or action chunks |
| Robot boundary | fake/tabletop, byte transport, persistent HTTP, ROS 2 mapping, and `rclpy` runtime | observations, command ACKs, stop events |
| Reproducibility | scenario suites, episode replay, dataset export, held-out and leave-one-scenario-out baselines | deterministic JSON artifacts |

## Deliberately not claimed

- The injected planner latency in the bundled boundary suite is fixture data, not live-provider latency.
- DeepSeek, Qwen, and GLM are supported through one provider-neutral adapter but have not been accepted on current live endpoints.
- The local KNN/Ridge policies are behavior-cloning baselines, not ACT, SmolVLA, or a production VLA.
- ROS 2 topic bindings and Gazebo assets do not prove that robot dynamics have run.
- No Unitree G1 adapter, physical robot, live EEG device, clinical claim, or safety certification exists.

## Commands

```bash
PYTHONPATH=src python3 -m synapse2action --contract-catalog --output artifacts/contracts.json
PYTHONPATH=src python3 -m synapse2action --planner-benchmark experiments/planner --output artifacts/planner-boundary.json
PYTHONPATH=src python3 -m synapse2action --planner-live-benchmark experiments/planner_live --planner-base-url http://localhost:8000/v1 --planner-model your-model-name --output artifacts/planner-live.json
PYTHONPATH=src python3 -m synapse2action --keyboard-intents --output artifacts/keyboard-session.json
PYTHONPATH=src python3 -m synapse2action --demo-suite experiments/demos --artifact-directory artifacts/demo-suite --output artifacts/demo-suite.json
```

## Gate before dynamic simulation

The pre-simulation layer is acceptable when contract generation succeeds, all deterministic scenario and planner-boundary cases pass, no invalid plan reaches a robot, provider failure terminates in `failed`, stop preempts every reachable tested state, and identical deterministic inputs produce identical reports. Live-provider reports are intentionally non-deterministic in timing and remain a separate evidence track.
