# Policy Model Card / Policy 模型卡

**Card version:** 1
**Date:** 2026-08-31
**Scope:** policy components evaluated or staged by Synapse2Action

This card distinguishes code integration, local evaluation, and released model
artifacts. A listed model is not automatically qualified for a robot.

本卡区分代码集成、本地评测与已发布模型资产；列入清单不等于通过机器人准入。

## Released deterministic baselines / 已发布确定性基线

`ScriptedPolicy`, KNN VLA, Ridge VLA, and Temporal Ridge VLA are implemented in
this repository. Their checkpoints are generated deterministically from the
published synthetic navigation scenarios during tests; no opaque pretrained
binary is required for the CPU acceptance profile.

仓库包含 `ScriptedPolicy`、KNN VLA、Ridge VLA 和 Temporal Ridge VLA。测试会从
已发布的合成 Navigation Scenario 确定性生成 Checkpoint；CPU 验收不需要不透明
预训练二进制。

**Intended use:** contract tests, closed-loop navigation baselines, adapter and
verifier regression.
**Not intended:** manipulation foundation-model claims, physical G1 control,
clinical use, or production autonomy.
**Known limits:** synthetic geometry, narrow action space, no contact dynamics,
no proof of transfer outside the published scenarios.

## SmolVLA / SmolVLA

The upstream `lerobot/smolvla_base` identity and LeRobot version are pinned in
`simulation/vla.lock.json`. Synapse2Action has locally fine-tuned and evaluated
a G1-oriented checkpoint, but its checkpoint, training dataset, and rollout
reports are ignored local artifacts and are not distributed by this release.
README metrics describe a specific prior local run and are not independently
reproducible from the public Git tree alone.

上游 `lerobot/smolvla_base` 与 LeRobot 版本固定在 `simulation/vla.lock.json`。
项目曾在本地微调并评测面向 G1 的 Checkpoint，但 Checkpoint、训练数据和 Rollout
报告均为被忽略的本地产物，本 Release 不分发。README 指标描述特定历史本地运行，
仅凭公开 Git Tree 无法独立复现。

## GR00T N1.6 / GR00T N1.6

The public checkpoint and whole-body-controller source identities are recorded
in repository locks and references. Model weights, vendor runtime, videos, and
the 20-seed raw evidence are not redistributed. The measured 1/20 strict success
rate is a local MuJoCo finding, not a released checkpoint qualification and not
physical-G1 evidence.

公开 Checkpoint 与 Whole-Body Controller 源码身份记录在 Lock 和参考材料中；
模型权重、Vendor Runtime、视频和 20-Seed 原始证据不随仓库分发。1/20 严格成功率
是本地 MuJoCo 结论，不构成已发布 Checkpoint 准入，更不是真机证据。

## OpenPI / OpenPI

OpenPI is pinned as source reference and connected through a tested proposal
adapter requiring explicit observation encoding and embodiment mapping. No
OpenPI checkpoint has passed the repository TaskSpec, seed, language, motion,
and evidence gates. The integration is a protocol capability only.

OpenPI 已作为源码参考固定，并通过要求显式 Observation Encoding 和 Embodiment
Mapping 的提案 Adapter 接入；尚无 OpenPI Checkpoint 通过本仓库 TaskSpec、Seed、
语言、运动和证据门。当前仅证明协议集成能力。

## Routing and admission / 路由与准入

Versioned manifests for GR00T, SmolVLA, and OpenPI are published under
`policies/`. All three are marked `candidate`, not `admitted`. Automatic
production selection accepts only a uniquely matched admitted Policy with
immutable evidence; supervised research must explicitly opt into a named
candidate.

GR00T、SmolVLA 与 OpenPI 的版本化 Manifest 位于 `policies/`。三者当前均标记为
`candidate`，而非 `admitted`。生产自动选择只接受唯一匹配、具有不可变证据的已准入
Policy；受监督研究必须显式启用指定 Candidate。

## Safety and evaluation / 安全与评测

All learned outputs are untrusted proposals. Harness confirmation, deterministic
motion limits, controller safety, emergency stop, and independent outcome
verification remain outside the model. Qualification requires matched seeds,
language counterfactuals, Result v3 evidence, bounded recovery, and an immutable
evidence bundle. See `RESPONSIBLE_USE.md` and `docs/industrialization-gap.md`.

所有学习模型输出都是不可信提案。Harness 确认、确定性运动限制、Controller 安全、
急停和独立结果验证均位于模型之外。准入必须覆盖匹配 Seed、语言反事实、Result v3、
受限恢复和不可覆盖证据包。
