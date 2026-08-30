# Product Console Architecture

## Goal

Provide one local browser console that lets a supervised operator understand and control the complete loop:

`human input -> Intent -> LLM Planner -> plan review -> VLA -> controller -> robot -> observation -> verification`

The first supported deployment is a Windows browser connected to the runtime in WSL2 on the same workstation. The console is an operator surface and evidence viewer. It is not a replacement for a hardware emergency-stop circuit.

## Product boundary

The console has three planes with deliberately different authority.

| Plane | Owns | Browser authority |
| --- | --- | --- |
| Experience | live camera, task, stage state, metrics, evidence | read and navigate |
| Orchestration | start, simulation stop, plan authorization, run history | authenticated operator commands |
| Safety | torque disable, watchdog, joint limits, collision limits, physical E-Stop | status only; hardware path remains independent |

The browser may stop a local simulation process. A future physical G1 adapter must expose a separately verified stop acknowledgement from the robot safety controller. The UI must never label a process termination as a hardware E-Stop.

## Deployment

```text
Windows browser
    | localhost:8765 + access token
WSL2 mission console
    | state API + frame stream + reports
Harness
    | typed TaskSpec and authorization gate
LLM Planner -> VLA policy -> WBC/SDK2 -> MuJoCo or G1
    ^                                      |
    +----------- observations ------------+
```

The current server uses Python's standard library, binds to `127.0.0.1` by default, and has no CDN or external web dependency. WSL2 localhost forwarding makes it available to the Windows browser without exposing it to the LAN. Remote access requires a separate TLS reverse proxy and identity layer; changing `--host` to `0.0.0.0` is not a production deployment.

## Screens

### Mission control

- Live MuJoCo camera feed with an explicit connected, stale, or unavailable state.
- One primary action: authorize a simulation run.
- A spatially separated simulation-stop action.
- Eight-stage execution timeline from dataset input through physical verification.
- Current outcome and a bounded diagnostic log.

### Plan review

- Human-readable instruction and typed `TaskSpec` shown together.
- Planner provider, model, latency, and validation result.
- Confirm and cancel remain distinct intent events with an expiry time.
- Any target, world revision, policy, or safety-profile change invalidates prior authorization.

### Evidence and history

- Every run receives an immutable run identifier.
- Store task, model and policy identity, code revision, seed, timings, outcome checks, and evidence paths.
- Replay uses recorded video and telemetry; it never presents replay as live state.
- Benchmark summaries separate outcome, process compliance, and safety violations.

## Runtime contracts

The product should converge on these stable interfaces rather than binding the UI to a particular model:

- `IntentEvent`: source, kind, confidence, timestamp, and sequence.
- `TaskSpec`: instruction, skill, typed arguments, constraints, and display labels.
- `PlanAuthorization`: task hash, world revision, expiry, operator, and decision.
- `PolicySession`: full model ID, checkpoint revision, policy adapter, observation and action schema.
- `RunEvent`: monotonic sequence, stage, state, timestamp, and bounded detail.
- `SafetyState`: mode, watchdog, stop chain, limit status, and last acknowledgement.
- `EvidenceManifest`: run identity, artifacts, checksums, verdicts, and provenance.

LeRobot should own dataset and policy lifecycle conventions. Synapse2Action owns intent, plan authorization, safety gating, orchestration, and evidence semantics. GR00T and other mature policies plug in behind the same policy boundary.

## Delivery gates

### Console MVP

- Windows opens the WSL2 console through localhost.
- Live SmolVLA/MuJoCo frames and stage events are visible.
- Start requires an explicit operator confirmation.
- Simulation stop terminates the active process group and is recorded.
- Keyboard focus, reduced motion, mobile fallback, and bilingual labels work.

### Research product

- GR00T live frame and telemetry adapter.
- Run history, report replay, benchmark comparison, and artifact export.
- Server-sent events instead of polling, with sequence recovery and stale-state detection.
- Policy and TaskSpec selection from an allowlist, never arbitrary shell arguments.
- Role-based authorization and append-only audit records.

### Hardware pilot

- G1 hardware adapter with heartbeat and command acknowledgement.
- Independent safety controller and physical E-Stop verification.
- Simulation, shadow, reduced-speed, and enabled modes with distinct visual states.
- Preflight checklist, workspace exclusion zones, joint and velocity limits, and automatic safe hold.
- Fault injection and recovery tests before supervised hardware trials.

### Product release

- Signed releases and locked model, controller, and task versions.
- Reproducible evidence bundles and retention policy.
- Operator onboarding, incident workflow, observability, and update rollback.
- Safety and regulatory review appropriate to the actual deployment environment.

## Current limitations

- The interactive live frame path is currently implemented for the SmolVLA MuJoCo runner. GR00T produces stronger post-run video evidence but still needs a live-frame adapter.
- The console has token protection but not user identity, roles, TLS, or durable audit storage.
- The stop endpoint terminates the active local process group. It does not prove that a physical robot stopped.
- Polling at 500 ms is sufficient for the local MVP, not for multi-client or remote operation.
- Twenty fixed seeds establish the current 5% strict-success baseline; they do not establish product reliability or physical-robot performance.
