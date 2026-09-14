# Third-party notices / 第三方声明

Original Synapse2Action code is licensed under the [MIT License](LICENSE).
The files listed below contain adaptations of upstream code and are distributed
under Apache-2.0. The root MIT license does not replace their upstream terms.

Synapse2Action 原创代码采用 [MIT 许可证](LICENSE)。下列文件包含上游代码的改编，
以 Apache-2.0 分发；根目录的 MIT 许可证不替代其上游条款。

## Unitree RL Lab controller adaptations / 控制器改编

- Upstream / 上游：[unitreerobotics/unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab)
- Source revision / 源码版本：`4960b84732b0c2ec593dccbfe963fda1bcd7b1e3`
- License / 许可：[Apache-2.0 text](LICENSES/Apache-2.0.txt), copied unchanged from the pinned upstream [LICENCE](https://github.com/unitreerobotics/unitree_rl_lab/blob/4960b84732b0c2ec593dccbfe963fda1bcd7b1e3/LICENCE).

| Distributed file / 分发文件 | Upstream file / 上游文件 | Synapse2Action modifications / 本项目修改 |
| --- | --- | --- |
| [g1_state_rlbase.cpp](simulation/cpp/g1_state_rlbase.cpp) | [State_RLBase.cpp](https://github.com/unitreerobotics/unitree_rl_lab/blob/4960b84732b0c2ec593dccbfe963fda1bcd7b1e3/deploy/robots/g1_29dof/src/State_RLBase.cpp) | Keyboard command handling and environment-configured manipulation poses, joint mapping, interpolation, and timing. / 键盘指令处理及环境变量配置的操作姿态、关节映射、插值与时序。 |
| [g1_velocity_main.cpp](simulation/cpp/g1_velocity_main.cpp) | [main.cpp](https://github.com/unitreerobotics/unitree_rl_lab/blob/4960b84732b0c2ec593dccbfe963fda1bcd7b1e3/deploy/robots/g1_29dof/main.cpp) | Simulation startup, odometry-driven velocity commands, target tracking, and obstacle detours. / 仿真启动、里程计驱动速度指令、目标跟踪与障碍绕行。 |

The upstream license text includes the notice “Copyright 2024 The Isaac Lab
Project Developers”; it is retained in the bundled license. The pinned upstream
repository has no root NOTICE file. These acknowledgments do not imply upstream
endorsement of Synapse2Action or its modifications.

随附许可证保留上游的“Copyright 2024 The Isaac Lab Project Developers”声明。
锁定版本的上游仓库根目录没有 NOTICE 文件。上述致谢不代表上游对本项目或其修改的背书。

## External dependencies and assets / 外部依赖与资产

The [dependency register](docs/references.md) identifies other libraries, model
weights, datasets, and research references. Their inclusion in a runtime or
Docker image remains subject to their own licenses; this file does not
relicense them. Preserve the applicable upstream license and attribution files
when redistributing those dependencies.

[依赖登记表](docs/references.md)列出其他软件库、模型权重、数据集与研究参考。
运行时或 Docker 镜像中的第三方依赖仍遵循各自许可，本文件不对其重新许可。
再分发这些依赖时，应保留适用的上游许可证与署名文件。
