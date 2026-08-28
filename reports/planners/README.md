# Planner acceptance evidence

## yuesheng-vllm/model

Verified on 2026-08-28 against the self-hosted DeepSeek V4 Flash route configured in Pi Agent.

- Output mode: `prompt-json`; the endpoint did not reliably support `response_format=json_schema`.
- Local validation: strict Plan v2 decoder, unchanged acceptance thresholds.
- Result: 6/6 cases, `accepted=true`.
- Schema compliance: 1.0.
- Unsafe action executions: 0.
- Provider errors: 0.
- Median latency: 1607.130 ms.
- P95 latency: 3667.721 ms.
- Report digest: recorded in `provider-summary.json`.

## qwen-vllm/Qwen3.8-Flash-Next

- Output mode: `prompt-json` with zero normalized outputs.
- Result: 6/6 cases, `accepted=true`.
- Schema compliance: 1.0.
- Unsafe action executions and provider errors: 0.
- P95 latency: 1851.872 ms.

## bigmodel/glm-5.3

- Output mode: `prompt-json`; two exact JSON fences were visibly normalized.
- Result: 6/6 cases, `accepted=true`.
- Schema compliance: 1.0.
- Unsafe action executions and provider errors: 0.
- P95 latency: 8542.013 ms.

## Aggregate

`provider-summary.json` requires all three identities, records each report digest, and has `accepted=true` with no missing or rejected model.

The separate `rtxpro-vllm/DeepSeek-V4-Flash-0731` Pi route was not accepted: its real smoke request returned `502 upstream unavailable` through all retries. It is not represented by the successful yuesheng artifact.
