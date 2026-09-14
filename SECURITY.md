# Security Policy / 安全政策

## Supported scope / 支持范围

Security fixes target the current `main` branch. Historical experiment outputs,
vendor checkouts, and unmaintained local deployment copies are not supported
releases. A tagged release must publish its own support status before it is
treated as deployable.

安全修复面向当前 `main`。历史实验输出、Vendor Checkout 和无人维护的本地部署
副本不属于受支持 Release；Tag 必须独立声明支持状态后才能视为可部署版本。

## Reporting a vulnerability / 漏洞报告

Do not include exploit details, credentials, human recordings, robot network
addresses, or unsafe actuation procedures in a public issue. Use GitHub's
private vulnerability-reporting [form](https://github.com/ZacharyZcR/Synapse2Action/security/advisories/new)
for this repository when it is available.
If the form is unavailable, contact the repository owner through an existing
trusted private channel and disclose only the minimum information needed to
establish contact. GitHub provides this feature for public repositories;
a `404` while the repository is private does not establish an enablement failure.
When making the repository public, maintainers must enable private reporting
and verify that the form is accessible before advertising it as available.

禁止在公开 Issue 中包含利用细节、凭据、真人记录、机器人网络地址或危险驱动
步骤。GitHub Private Vulnerability Reporting 的[私密报告入口](https://github.com/ZacharyZcR/Synapse2Action/security/advisories/new)
可用时应优先使用；若不可用，
通过已有可信私密渠道联系仓库所有者，并只发送建立联系所需的最少信息。
GitHub 面向公开仓库提供此功能；仓库处于 Private 时的 `404` 不足以判定启用失败。
维护者将仓库公开后，必须启用并验证报告表单可访问，再对外宣称该入口可用。

See [GitHub's configuration instructions](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).
具体配置见 [GitHub 官方说明](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)。

Include the affected revision, boundary, prerequisites, impact, safe reproducer,
and whether physical hardware or personal data is involved. Maintainers should
acknowledge a valid private report within seven days, agree on a remediation
plan, and coordinate disclosure after affected credentials and deployments are
secured. These are response targets, not a warranty.

报告应包含受影响 Revision、边界、前置条件、影响、安全复现方式，以及是否涉及
真机或个人数据。Maintainer 目标是在七天内确认有效私密报告、协商修复计划，并
在相关凭据和部署完成保护后协调披露；该时限是响应目标，不是保证。

## Security invariants / 安全不变量

- LLM/VLA output never owns emergency stop, collision enforcement, torque,
  velocity, workspace limits, or the final success verdict.
- Unknown, malformed, stale, unconfirmed, or out-of-bounds commands fail closed.
- Secrets never enter source, reports, traces, screenshots, or evidence bundles.
- Evidence integrity does not imply authenticity unless its digest is retained
  externally or signed by a trusted release process.
- Security tests use simulators, loopback transports, fixtures, or authorized
  laboratory systems; production and third-party robots are out of scope.

- LLM/VLA 永远不拥有急停、碰撞、力矩、速度、工作空间限制或最终成功判定权。
- 未知、非法、过期、未确认或越界命令必须 Fail Closed。
- 凭据不得进入源码、报告、Trace、截图或证据包。
- 证据完整性不等于真实性；根 Digest 必须外部留存或由可信发布流程签名。
- 安全测试仅使用仿真器、Loopback、Fixture 或获授权实验室系统；生产环境与
  第三方机器人不在范围内。
