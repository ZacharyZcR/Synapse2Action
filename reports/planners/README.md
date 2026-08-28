# Planner acceptance evidence

## yuesheng-vllm/model

Verified on 2026-08-28 against the self-hosted DeepSeek V4 Flash route configured in Pi Agent.

- Output mode: `prompt-json`; the endpoint did not reliably support `response_format=json_schema`.
- Local validation: strict Plan v2 decoder, unchanged acceptance thresholds.
- Result: 6/6 cases, `accepted=true`.
- Schema compliance: 1.0.
- Unsafe action executions: 0.
- Provider errors: 0.
- Median latency: 2370.092 ms.
- P95 latency: 4836.341 ms.
- Report digest: recorded in `provider-summary.json`.

The separate `rtxpro-vllm/DeepSeek-V4-Flash-0731` Pi route was not accepted: its real smoke request returned `502 upstream unavailable` through all retries. It is not represented by the successful yuesheng artifact.
