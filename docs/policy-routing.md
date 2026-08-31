# Policy Routing and Lifecycle / Policy 路由与生命周期

Synapse2Action may use different models for different physical jobs, but an LLM
does not select or load a Policy. The LLM produces a validated TaskSpec; the
deterministic registry matches that TaskSpec, the robot embodiment, and an
admission state against versioned manifests in [`policies/`](../policies/).

Synapse2Action 可以针对不同物理工作使用不同模型，但 LLM 无权选择或加载 Policy。LLM
只生成经过校验的 TaskSpec；确定性注册表使用该 TaskSpec、机器人本体和准入状态匹配
[`policies/`](../policies/)中的版本化 Manifest。

```text
validated TaskSpec
→ capability match: task + skill + embodiment
→ admitted-only selection
→ operator review and confirmation
→ activate Policy
→ clear old action chunks and observation history
→ execute
→ independent verification
```

## Manifest contract / Manifest 契约

Each manifest identifies the Policy and release, supported TaskSpec IDs and
skills, embodiment, camera/state requirements, action representation and rate,
and admission evidence. `admitted` requires an immutable evidence-bundle path
and SHA-256 digest. A `candidate` cannot claim admission evidence.

每份 Manifest 记录 Policy 与 Release、支持的 TaskSpec ID 和 Skill、本体、相机与状态要求、
动作表示与频率，以及准入证据。`admitted` 必须绑定不可变证据包路径和 SHA-256；
`candidate` 不得声称具有准入证据。

The published GR00T, SmolVLA, and OpenPI manifests are currently candidates.
None is marked admitted: GR00T has only 1/20 strict all-stage success, and the
other candidates lack complete matched Policy Admission evidence. Therefore
`--policy auto` correctly refuses current production execution.

当前发布的 GR00T、SmolVLA 与 OpenPI Manifest 均为 Candidate，没有任何一个被标记为
Admitted：GR00T 严格全阶段成功率仅为 1/20，其他候选也缺少完整匹配的 Policy Admission
证据。因此当前生产模式使用 `--policy auto` 会正确拒绝执行。

Supervised research may request an exact candidate with
`--allow-candidate-policy`. This flag is an explicit claim downgrade, not a
production admission shortcut. Test-only Mock or Scripted components remain
separately gated by `--allow-test-doubles`.

受监督研究可以使用 `--allow-candidate-policy` 指定准确 Candidate。该参数明确降低能力
声明，不是绕过生产准入的捷径。Mock 与 Scripted 测试替身仍由独立的
`--allow-test-doubles` 控制。

## Switching rules / 切换规则

A Policy cannot change while executing. Switching an already active Policy
requires this exact order: deterministic safe stop, clear pending action chunks,
reset observation history, then activate the new Policy. A missing match,
multiple matches, wrong embodiment, candidate-only match, or unconfigured
runtime fails closed.

Policy 执行期间禁止切换。已有 Policy 激活时，切换顺序必须是：确定性安全停止、清空待执行
Action Chunk、重置 Observation History，最后激活新 Policy。缺少匹配、存在多个匹配、本体
不符、只有 Candidate 或 Runtime 未配置时一律 Fail-Closed。
