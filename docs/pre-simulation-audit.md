# Pre-simulation completion audit

Scope: all deterministic software and provider boundaries required before introducing robot dynamics. Gazebo execution, Unitree G1 dynamics, physical hardware, and live EEG acquisition are later phases.

| Requirement | Status | Authoritative evidence |
|---|---|---|
| Python 3.12+ package | Proven | `pyproject.toml` `requires-python` |
| Versioned intent, world, plan, skill, action, and result contracts | Proven | `schemas.py`, `--contract-catalog`, contract-schema tests |
| Replaceable IntentSource, Planner, Policy, Robot, Verifier boundaries | Proven | Protocols in `contracts.py`; scripted and keyboard source tests |
| Explicit state machine and confirmation gate | Proven | `Harness`; authorization, harness, and scenario suites |
| Stop preemption and no unconfirmed robot action | Proven for deterministic state space through length five | exhaustive property-style state-machine tests |
| Typed skills, argument validation, timeout, and outcome checks | Proven | `SkillRegistry`; skill and adversarial scenario tests |
| Deterministic replay and reports | Proven | scenario, EEG, VLA episode, demo-suite, and benchmark equality tests |
| OpenAI-compatible Planner replacement | Proven at adapter and loopback HTTP boundaries | embedded Planner HTTP test and complete demo |
| Plan v2 execute/refuse semantics | Proven locally | strict decoder tests, provider-native refusal test, eight-case boundary suite |
| Prompt-injection-shaped target identifiers rejected before network | Proven | identifier validation and live-suite mock call count |
| Provider failure contained before robot | Proven | timeout boundary case and Harness failure trace |
| Common live-provider acceptance runner | Proven with a mock compatible provider | six-case live suite; explicit thresholds; latency and safety metrics |
| Multi-provider evidence matrix | Proven with fixture reports | strict report loader, required-model gate, unique names, artifact SHA-256 digests |
| yuesheng-vllm DeepSeek V4 Flash live acceptance | Proven | `reports/planners/yuesheng-vllm-model.json`: 6/6, schema compliance 1.0, zero unsafe executions/errors, p95 3667.721 ms |
| Qwen3.8-Flash-Next live acceptance | Proven | `reports/planners/qwen-vllm-qwen38-flash-next.json`: 6/6, schema compliance 1.0, zero unsafe executions/errors, p95 1851.872 ms |
| GLM-5.3 live acceptance | Proven with visible normalization | `reports/planners/bigmodel-glm-5.3.json`: 6/6, schema compliance 1.0, zero unsafe executions/errors, two fenced outputs normalized, p95 8542.013 ms |
| Three-provider evidence matrix | Proven | `reports/planners/provider-summary.json`: all required identities present, no rejected models, `accepted=true`, report SHA-256 digests retained |
| Alternate rtxpro-vllm DeepSeek-V4-Flash-0731 route | Non-blocking unavailable alternative | Pi route resolved, but the real smoke request returned `502 upstream unavailable` after retries; it is not substituted for the accepted yuesheng identity |

The deterministic pre-simulation implementation and required provider evidence are complete when all proven rows remain green. Named providers are accepted independently: each retained report has `accepted=true`; adapter compatibility alone is not treated as evidence. The yuesheng report proves only that provider/model identity and must not be relabeled as the unavailable rtxpro route.
