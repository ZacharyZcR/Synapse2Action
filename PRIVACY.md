# Privacy Policy / 隐私政策

This policy covers research data handled by Synapse2Action contributors. It is
not a consumer privacy notice and does not authorize collection from people.

本政策约束 Synapse2Action 贡献者处理研究数据，不是面向消费者的隐私声明，也
不构成采集人体数据的授权。

## Sensitive data / 敏感数据

Raw or derived EEG, event timing, calibration profiles, subject identifiers,
camera/audio recordings, biometrics, operator behavior, network identifiers,
and free-text instructions may identify a person or reveal health and workplace
information. Treat them as sensitive even when names have been removed.

原始或派生 EEG、事件时序、校准 Profile、受试者标识、音视频、生物特征、操作员
行为、网络标识和自由文本指令都可能识别个人或泄露健康与工作场所信息；删除
姓名后仍按敏感数据处理。

## Collection and consent / 采集与同意

- Obtain applicable ethics/IRB approval and explicit informed consent before
  collecting human data. Consent must cover purpose, sensors, retention,
  sharing, withdrawal, incidental recording, and robot-related risks.
- Collect only channels and metadata required by a written protocol. Do not use
  safety logs or operator recordings for model training without separate consent.
- A participant's withdrawal must stop future use where legally and technically
  possible; immutable published aggregates must be disclosed during consent.

- 采集真人数据前取得适用的伦理/IRB 批准和明确知情同意；同意内容应覆盖目的、
  Sensor、留存、共享、撤回、意外录制和机器人风险。
- 只采集书面协议要求的通道和元数据；未经独立同意，不得将安全日志或操作员
  录制用于模型训练。
- 在法律和技术允许范围内，撤回应停止后续使用；无法撤回的已发布聚合结果必须
  在知情同意时说明。

## Storage and release / 存储与发布

Keep identifiable data outside Git, encrypt it at rest and in transit, restrict
access by role, separate participant identity from session IDs, and record
access and deletion. Define a retention deadline before collection. Public
artifacts should contain synthetic data, consented de-identified samples, or
aggregates that have passed disclosure review. Hashes are identifiers, not
anonymization.

可识别数据必须置于 Git 之外，静态和传输时加密，按角色限制访问，将身份映射与
Session ID 分离，并记录访问和删除。采集前必须确定留存期限。公开产物只能包含
合成数据、经同意且去标识的数据或通过披露审查的聚合结果。Hash 是标识符，不是
匿名化手段。

## Incident handling / 事件处理

On suspected exposure, stop further collection and sharing, preserve minimal
audit evidence, revoke affected credentials, notify the data controller and
ethics authority, assess notification duties, and document remediation without
republishing the exposed data.

疑似泄露时应停止继续采集和共享，保留最少审计证据，撤销相关凭据，通知数据
Controller 与伦理机构，评估通知义务，并在不重新发布泄露数据的前提下记录修复。
