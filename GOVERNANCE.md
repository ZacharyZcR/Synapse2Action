# Governance / 治理

## Authority / 决策权

The repository owner is the maintainer of record and has final responsibility
for releases, repository access, safety claims, and changes to control
authority. Contributors may propose and review changes but do not gain release
or robot-operation authority through code contribution alone.

仓库所有者是当前登记 Maintainer，对 Release、仓库权限、安全声明及控制权变更
承担最终责任。贡献代码本身不会自动授予发布或机器人操作权限。

## Decision process / 决策流程

- Ordinary fixes use review, focused tests, and documented evidence.
- Contract, evidence-schema, safety-limit, dependency, and architecture changes
  require an issue or discussion that records alternatives and migration impact.
- A release must identify its code revision, policy/model, dataset, controller,
  acceptance thresholds, unresolved failures, and evidence-bundle digest.
- A safety objection blocks increased execution authority until resolved with
  deterministic tests or measured evidence.

- 普通修复通过 Review、针对性测试和证据记录决策。
- 契约、证据 Schema、安全限制、依赖及架构变更必须通过 Issue 或 Discussion
  记录替代方案和迁移影响。
- Release 必须标明代码 Revision、Policy/模型、数据集、Controller、准入阈值、
  未解决失败和证据包 Digest。
- 安全异议在通过确定性测试或实测证据解决前，阻止扩大执行权限。

## Capability claims / 能力声明

Claims are scoped to the exact tested embodiment and environment. MuJoCo is not
physical-G1 evidence; public dataset replay is not a live human-intent result;
transport success is not policy causality; and one successful rollout is not a
reliability claim. Corrections to overstated claims do not require consensus.

能力声明只适用于精确测试过的本体和环境。MuJoCo 不等于 G1 真机证据；公开数据
回放不等于实时真人意图；数据传递成功不等于 Policy 因果贡献；单次成功不等于
可靠性。纠正夸大声明无需等待共识。

## Changes to governance / 治理变更

Governance changes use normal review but must explain whose authority, data, or
safety responsibility changes. This document does not delegate physical robot
authorization, emergency-stop ownership, or access to sensitive recordings.

治理变更必须说明谁的权限、数据或安全责任发生变化。本文件不授予真机执行、
急停控制或敏感记录访问权。
