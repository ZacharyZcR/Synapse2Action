# Engineering Philosophy / 工程哲学

## From biological intent to embodied action / 从生物意图到具身行动

Synapse2Action is a biomimetic embodied-intelligence engineering project. Its goal is not merely to use EEG as a remote-control input or to connect several AI models. The project reconstructs the functional path from human intention to physical action as a layered artificial nervous and motor system.

Synapse2Action 是一个仿生具身智能工程项目。它的目标不只是把 EEG 当作遥控输入，也不是简单串联多个 AI 模型，而是以工程方式重建从人类意图到物理行动的功能链路，形成分层的人工神经与运动系统。

> From biological intent, through synthetic cognition, to embodied action.
>
> 从生物意图，经人工认知，到具身行动。

## Functional biomimetic mapping / 仿生功能映射

| Biological function / 生物功能 | Engineering system / 工程系统 | Responsibility / 职责 |
|---|---|---|
| Conscious intention / 有意识意图 | EEG acquisition and decoding | Sense sparse human intent such as selection, confirmation, cancellation, and stop. / 感知选择、确认、取消和停止等稀疏真实意图。 |
| Higher cognition / 高级认知 | LLM Planner | Interpret intent in context, reason about the environment, and construct a task plan. / 结合环境理解意图并形成任务计划。 |
| Sensorimotor transformation / 感觉运动转换 | VLA | Convert visual observations, language goals, and proprioception into short-horizon action chunks. / 将视觉、语言目标和本体状态转换为短时动作块。 |
| Artificial spinal system / 人工脊髓系统 | VLA runtime, Action Chunk player, trajectory projection, IK/WBC, and local controllers | Transmit, shape, coordinate, and correct motor commands at operational timescales. / 在运动时间尺度上传递、整形、协调并修正动作信号。 |
| Reflex and balance / 反射与平衡 | Whole-body controller, watchdogs, limits, and emergency stop | Preserve balance and react locally without waiting for high-level cognition. / 无需等待高级认知即可保持平衡并作出局部反应。 |
| Musculoskeletal body / 肌肉骨骼系统 | Unitree SDK2, actuators, joints, and robot body | Convert bounded commands into force, movement, contact, and physical work. / 将受限命令转化为力、位移、接触和物理行为。 |
| Proprioception and sensation / 本体感觉与感知 | Cameras, encoders, IMU, contact and force signals | Close the loop by returning body and environment state. / 返回身体与环境状态，形成闭环。 |

This mapping is functional rather than anatomically literal. A VLA processes vision, language, and action and therefore resembles parts of the visual cortex, motor cortex, and cerebellar forward model. In this project, “artificial spinal system” names the complete operational layer formed by VLA action chunks plus deterministic projection and local control; it does not claim that a single neural model is anatomically equivalent to the human spinal cord.

这种映射强调功能对应，而不是字面解剖对应。VLA 同时处理视觉、语言和动作，在生物学上更接近视觉皮层、运动皮层和小脑前馈模型的一部分。本项目所称“人工脊髓系统”，指 VLA Action Chunk、确定性投影和局部控制共同形成的运动执行层，并不声称某一个神经模型在解剖意义上等同于人类脊髓。

## Multiple timescales / 多时间尺度

The layers must not run as one synchronous request chain. Biological motor control separates deliberate cognition from fast coordination and reflexes; the engineering system must do the same.

各层不能被设计成一条同步等待的请求链。生物运动系统会把有意识认知与快速协调、反射分开，工程系统也必须如此。

| Layer / 层级 | Indicative rate / 参考频率 | Engineering meaning / 工程含义 |
|---|---:|---|
| EEG intention | 0.2–2 Hz | Sparse deliberate choice, not continuous joint control. / 稀疏有意识选择，而非连续关节控制。 |
| LLM cognition | Event driven | Plan only when intent or task context changes. / 仅在意图或任务上下文变化时规划。 |
| VLA sensorimotor policy | 3–30 Hz | Generate short action chunks from current observations. / 根据当前观测生成短时动作块。 |
| Trajectory and whole-body coordination | 50–200 Hz | Interpolate, constrain, and coordinate the body. / 插值、约束并协调全身动作。 |
| Balance and local reflex | 200–1000 Hz | Maintain stability and react to disturbances. / 保持稳定并响应扰动。 |
| Actuator loop | Native robot rate | Apply force and position control. / 执行力与位置控制。 |

An LLM must never be responsible for millisecond balance. A low-rate VLA must never be the only mechanism preventing a fall. High-level intelligence creates goals and motor patterns; fast local systems preserve the body.

LLM 不能负责毫秒级平衡，低频 VLA 也不能成为防止跌倒的唯一机制。高级智能负责目标和运动模式，快速局部系统负责维持身体。

## The primary engineering question / 首要工程问题

The project asks:

> Can real human intention be sensed through EEG, expanded by synthetic cognition, transformed by an artificial sensorimotor system, and expressed as stable physical behavior by a robotic body?

本项目研究的是：

> 人类真实意图能否通过 EEG 被感知，经人工认知扩展，由人工感觉运动系统转换，并最终通过机器人身体稳定地表达为物理行为？

This question contains four interfaces that must each be measured independently:

1. **Intention interface:** whether EEG decoding reflects the intended selection and confirmation.
2. **Cognitive interface:** whether the LLM produces a contextually correct and executable plan.
3. **Sensorimotor interface:** whether VLA action chunks improve closed-loop behavior from current observations.
4. **Physical interface:** whether whole-body control converts actions into stable, repeatable task completion.

这一问题包含四个必须独立测量的接口：意图是否被正确感知、认知计划是否正确可执行、VLA 是否根据当前观测改善闭环动作、全身控制是否能稳定重复地完成物理任务。

## Engineering principles / 工程原则

### Closed loop before spectacle / 闭环优先于展示

Every action layer must consume current observations and produce measurable state change. A visually convincing video or a single accepted rollout is not sufficient evidence.

每个动作层都必须读取当前观测并产生可测量的状态变化。漂亮视频或单次成功 rollout 不能构成充分证据。

### Functional necessity before model accumulation / 功能必要性优先于模型堆叠

Each model must have an indispensable role and a measurable ablation. If a deterministic lookup replaces the LLM without changing the task, that experiment does not demonstrate cognition. If disabling VLA does not change performance, that experiment does not demonstrate sensorimotor intelligence.

每个模型都必须承担不可替代的职责，并能通过消融实验测量。如果确定性查询可以无差别替代 LLM，该实验就没有证明认知能力；如果关闭 VLA 不影响结果，该实验就没有证明感觉运动智能。

### Stability is a system property / 稳定性是系统属性

Balance cannot be assigned to an isolated lower-body controller while independent upper-body motion and payload changes are added later. Waist, arms, contact, payload, center of mass, and locomotion must be represented in the whole-body control objective.

不能把平衡完全交给孤立的下肢 Controller，再独立叠加上肢动作和负载。腰部、双臂、接触、负载、质心和移动必须共同进入全身控制目标。

### Evidence must follow the hierarchy / 证据必须匹配层级

EEG accuracy, planner correctness, VLA action quality, controller stability, and task success are different claims. They must be reported separately before being combined into an end-to-end result.

EEG 准确率、Planner 正确性、VLA 动作质量、Controller 稳定性和任务成功率属于不同层级的主张，必须分别报告，再组合为端到端结果。

## Current implication / 对当前项目的含义

The present repeated-rollout failures indicate a break between the artificial spinal layer and the robotic body: the existing lower-body RL policy has not demonstrated stable coordination with upper-body manipulation and payload motion. This is now the main engineering problem. More planner prompts, frontend stages, or residual-weight tuning cannot substitute for a whole-body control architecture.

当前重复 rollout 的失败表明，人工脊髓层与机器人身体之间仍存在断点：现有下肢 RL Policy 尚未证明能够稳定协调上肢操作和携物运动。这是当前首要工程问题。继续增加 Planner Prompt、前端阶段或调整残差比例，都不能替代全身控制架构。

The next milestone should therefore be defined around a whole-body sensorimotor loop and repeated stability evidence, while EEG and LLM remain connected through stable interfaces but do not dominate controller development.

因此，下一里程碑应围绕全身感觉运动闭环和重复稳定性证据展开。EEG 与 LLM 继续通过稳定接口保留在系统中，但不应主导当前 Controller 开发。

