# Contributing / 贡献指南

Synapse2Action accepts changes that preserve its safety authority and evidence
boundaries. A demonstration, upstream claim, or passing mock is not evidence of
physical capability.

Synapse2Action 接受不破坏安全控制权与证据边界的改动。演示、上游声明或通过
Mock 测试都不能作为真机能力证据。

## Before changing code / 修改代码前

1. Open an issue or discussion for changes to contracts, authority, safety
   limits, evidence schemas, or public capability claims.
2. Keep one change focused. Do not combine a bug fix with an unrelated model,
   dependency, or architecture migration.
3. Never commit credentials, raw human EEG, identifiable camera/audio data,
   private model artifacts, or vendor-licensed assets.
4. Record the exact model, data, controller, code revision, task, seed, and
   environment whenever a result is used as evidence.

1. 修改契约、控制权、安全限制、证据 Schema 或公开能力声明前，先建立 Issue
   或 Discussion。
2. 每次改动只解决一个问题；Bug Fix 不得夹带无关模型、依赖或架构迁移。
3. 禁止提交凭据、真人原始 EEG、可识别音视频、私有模型产物或受许可限制的
   Vendor 资产。
4. 任何作为证据的结果必须记录模型、数据、Controller、代码 Revision、任务、
   Seed 和环境。

## Required validation / 必需验证

Run the narrow tests covering the change, then the complete CPU suite:

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

Tests requiring loopback sockets need permission to bind `127.0.0.1`. Tests
requiring GR00T, MuJoCo vendor assets, GPU checkpoints, EEG hardware, or a robot
must be reported separately; do not replace them with mocks and claim the real
gate passed. Run `git diff --check` before committing.

需要 Loopback Socket 的测试必须能够绑定 `127.0.0.1`。依赖 GR00T、MuJoCo
Vendor 资产、GPU Checkpoint、EEG 设备或机器人的测试必须单独报告；不得用 Mock
替换后声称真实门槛已经通过。提交前运行 `git diff --check`。

## Pull request evidence / Pull Request 证据

A pull request must state scope, affected authority boundary, tests run, known
failures, external conditions not exercised, and documentation changed. New
adapters must implement an existing project contract where possible and prove
that malformed or stale model output cannot reach the robot boundary.

PR 必须说明范围、受影响的控制权边界、已运行测试、已知失败、未覆盖的外部条件
和文档改动。新 Adapter 应优先实现已有项目契约，并证明非法或过期模型输出无法
到达 Robot 边界。

By contributing, you confirm that you have the right to submit the material.
No license grant for third-party datasets, weights, recordings, or vendor code
is implied by their mention in this repository.

提交即表示贡献者有权提交相应材料；仓库对第三方数据集、权重、记录或 Vendor
代码的引用不构成再许可。
