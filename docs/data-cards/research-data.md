# Research Data Card / 研究数据卡

**Card version:** 1
**Date:** 2026-08-31
**Scope:** data referenced, generated, or distributed by Synapse2Action

## Data actually distributed in Git / Git 中实际分发的数据

- `experiments/scenarios/`: deterministic Harness success, rejection,
  authorization, world-drift, timeout, stop, and recovery fixtures.
- `experiments/navigation/`: synthetic 2D geometry and timing variations for
  closed-loop navigation.
- `experiments/intent_streams/` and `experiments/monte_carlo/`: synthetic intent
  and false-activation configurations.
- `experiments/planner*`: deterministic and live-provider prompt cases,
  including refusal, injection, malformed output, and unsafe requests.
- `experiments/tasks/`: three synthetic G1 TaskSpecs and language cases.
- `reports/planners/`: selected provider transcripts and aggregate results.

These files contain synthetic objects and prompts rather than participant EEG or
camera recordings. Planner reports may contain provider-generated text; they
must not be interpreted as model weights or physical-action evidence.

这些文件包含合成物体和 Prompt，不包含受试者 EEG 或相机记录。Planner Report
可能含 Provider 生成文本，但不属于模型权重或物理行为证据。

## Referenced but not redistributed / 引用但不再分发

MAMEM/WFDB EEG records remain with their original provider. Synapse2Action does
not redistribute raw human EEG. Users must obtain the records under upstream
terms and independently satisfy ethics, consent, privacy, and jurisdictional
requirements. Public origin does not remove biometric sensitivity.

MAMEM/WFDB EEG 原始记录仍由上游提供，Synapse2Action 不再分发真人原始 EEG。
使用者必须按上游条款自行获取，并独立满足伦理、知情同意、隐私和属地要求；公开
来源不消除生物特征敏感性。

Unitree/SmolVLA simulation episodes, LeRobot Dataset v3 trees, fine-tuned
checkpoints, camera frames, videos, and most EEG/simulation/training reports are
local ignored artifacts. Their presence on one maintainer workstation is not a
public dataset release. The research release catalog marks these explicitly as
`local-only`.

Unitree/SmolVLA Episode、LeRobot Dataset v3、微调 Checkpoint、相机帧、视频以及
多数 EEG/仿真/训练报告都是被忽略的本地产物。它们存在于某台 Maintainer 工作站
不等于公开数据发布；研究发布清单将其明确标记为 `local-only`。

## Generation and splits / 生成与划分

Synthetic scenario files are hand-authored versioned inputs. Navigation model
tests split whole episodes rather than individual frames and reject duplicate
episode content. Local G1 training uses independent timing-varied episodes and a
held-out episode, but those data are not part of this release. MAMEM experiment
splits and leakage limitations are documented in `docs/experiments.md`.

合成场景是人工编写的版本化输入。Navigation 模型按完整 Episode 而非 Frame 划分，
并拒绝重复 Episode 内容。本地 G1 训练使用独立时序变化 Episode 和留出 Episode，
但这些数据不属于本 Release。MAMEM 划分和泄漏限制见 `docs/experiments.md`。

## Privacy, license, and limitations / 隐私、许可与限制

No repository file authorizes collection of human data or relicenses upstream
datasets, model weights, or vendor assets. Follow `PRIVACY.md`, upstream terms,
and applicable review. Synthetic data underrepresent sensor noise, occlusion,
contact, hardware faults, human behavior, and distribution shift; performance
on them cannot establish clinical, physical, or production reliability.

仓库文件不授权采集人体数据，也不对上游数据集、模型权重或 Vendor 资产再许可。
必须遵守 `PRIVACY.md`、上游条款及适用审查。合成数据无法充分覆盖 Sensor 噪声、
遮挡、接触、硬件故障、人类行为和分布漂移，其结果不能证明临床、真机或生产可靠性。
