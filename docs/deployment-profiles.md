# Deployment Profiles / 部署配置

Deployment profiles separate reproducible execution conditions from capability
claims. A profile is complete only when its inputs, command, environment,
required assets, output report, and excluded claims are versioned and exercised.

部署 Profile 用于把可复现运行条件与能力声明分开。只有输入、命令、环境、所需
资产、输出报告和禁止声明均已版本化并实际运行时，Profile 才算完成。

| Profile | Status | External conditions | Evidence boundary |
|---|---|---|---|
| `cpu-ci` | Accepted / 已验收 | Python 3.12+, loopback sockets | Harness, contracts, deterministic simulations, adapters, verifiers, repository policies |
| Local GPU | Pending / 待完成 | Supported GPU, pinned drivers/runtime, model artifacts | Real model inference; not physical behavior |
| Vendor simulation | Pending / 待完成 | Pinned MuJoCo/vendor sources and checkpoints | Named simulator and embodiment only |
| Supervised physical | Pending / 待完成 | Robot, physical E-stop, operator, approved workspace and preflight | Exact robot/cell/task/revision only |

## CPU-only acceptance / 纯 CPU 验收

The source of truth is [`profiles/cpu-ci.json`](../profiles/cpu-ci.json). Run:

```bash
PYTHONPATH=src python3 simulation/run_cpu_ci.py \
  --report reports/cpu-ci.json
```

The runner discovers the complete repository test suite, requires Python 3.12
or newer, returns non-zero on any failure, and writes actual counts and platform
metadata. It installs nothing, accesses no external network, and requires no
model, simulator vendor tree, EEG hardware, or robot. Several tests use
temporary `127.0.0.1` servers, so loopback binding must be permitted.

Runner 会发现完整仓库测试，要求 Python 3.12+，任何失败均返回非零，并记录真实
测试数量和平台元数据。它不安装依赖、不访问外网，也不要求模型、Vendor 仿真树、
EEG 硬件或机器人；部分测试使用临时 `127.0.0.1` Server，因此必须允许 Loopback。

The generated report proves only hardware-free repository acceptance. It does
not prove live EEG performance, GPU inference, a vendor MuJoCo rollout, or
physical robot behavior. GitHub Actions runs the same command with read-only
repository permission and retains the report as an artifact.

生成报告只证明无设备仓库验收，不证明实时 EEG、GPU 推理、Vendor MuJoCo Rollout
或真机行为。GitHub Actions 使用只读仓库权限运行同一命令并保留报告 Artifact。

## Promotion rule / 晋级规则

Higher-authority profiles may reuse CPU acceptance but cannot inherit its
verdict. Each profile must name immutable runtime/model/controller revisions,
run its own readiness checks, preserve raw evidence, and state which lower-level
safety system retains control. Physical operation additionally requires the
preflight and human-override gates in [Responsible Use](../RESPONSIBLE_USE.md).

高权限 Profile 可以复用 CPU 验收，但不能继承其结论。每个 Profile 都必须记录
不可变 Runtime/模型/Controller Revision，执行独立 Readiness，保留原始证据，
并说明底层安全控制归属。真机还必须通过[负责任使用](../RESPONSIBLE_USE.md)规定的
Preflight 与人工接管门。
