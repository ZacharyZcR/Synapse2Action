# Research Release Catalog / 研究发布清单

Synapse2Action separates files present in Git from large, generated, licensed,
or machine-local assets. The source catalog is
[`research/release-source.json`](../research/release-source.json); the generated
[`research/release-v1.json`](../research/release-v1.json) records every published
file's collection, byte size, and SHA-256 digest.

Synapse2Action 严格区分 Git 内文件与大型、生成式、受许可限制或仅存在于本机的资产。源清单位于
[`research/release-source.json`](../research/release-source.json)，生成的
[`research/release-v1.json`](../research/release-v1.json)记录每个已发布文件的类别、字节数和 SHA-256。

## Included / 已包含

- experiment protocols and scenario JSON files;
- policy model and research data cards;
- published planner benchmark reports;
- dependency lock files and deployment profiles.

The manifest is built only from non-empty, repository-relative collections.
Symlinks, parent-directory traversal, duplicate membership, and missing
collections fail closed.

清单仅从非空的仓库相对路径集合生成；符号链接、父目录穿越、重复归类和空集合都会直接失败。

## Not published / 未发布

Raw EEG derivatives, model checkpoints, training datasets, generated rollouts,
MuJoCo evidence, physical-robot evidence, and vendored upstream repositories are
not part of this Git release. Their absence is recorded explicitly in the
manifest and must not be interpreted as reproducible evidence.

原始 EEG 衍生产物、模型权重、训练数据集、生成式 Rollout、MuJoCo 证据、真机证据及 Vendor 上游仓库均不属于本次 Git 发布。清单会明确记录这些缺口，不得把“本机曾经存在”解释为第三方可复现证据。

## Build and verify / 生成与验证

```bash
PYTHONPATH=src python3 simulation/build_research_release.py build
PYTHONPATH=src python3 simulation/build_research_release.py verify
```

The dependency-free CPU acceptance profile also verifies the checked manifest.
Any included file change therefore requires rebuilding it. SHA-256 detects
accidental or unauthorized modification; it is an integrity digest, not an
author signature or a license grant. Distribution rights and claim boundaries
remain governed by the model card, data card, repository policies, and upstream
licenses.

零依赖 CPU Acceptance Profile 同样会验证已提交清单，因此任何收录文件发生变化后都必须重新生成。SHA-256 用于发现意外或未授权修改，但它不是作者签名，也不授予再分发许可。分发权和能力口径仍由模型卡、数据卡、仓库政策及上游许可证约束。
