# Ubuntu OpenWBT / OpenTrack 仿真运行手册

本文用于在 Ubuntu 主机上验证 Synapse2Action 已锁定的 OpenWBT 与 OpenTrack G1 仿真路径。目标是先取得可审计的 Runtime Smoke 证据，再开展抓取后抬升对照实验。

> 当前边界：OpenWBT 是遥操作系统，OpenTrack 是动作跟踪系统。完成本手册不等于语言操作、物体抬升或真机能力已经通过。

## 1. 推荐环境

- Ubuntu 22.04 x86_64；OpenWBT 上游推荐 Ubuntu 20.04，若其依赖在 22.04 失败，使用独立的 20.04 主机或容器，不要修改系统 Python。
- NVIDIA GPU 与可用的 CUDA 12 驱动，用于 OpenTrack JAX 训练/评测。仅运行 C++ ONNX 部署 Smoke 时可不使用训练 GPU。
- Python 3.12.9 和 `uv`：OpenTrack。
- Conda Python 3.8：OpenWBT。
- 带图形桌面的会话用于 MuJoCo Viewer；无桌面时先跑 OpenTrack `--no-viewer`。
- 至少 80 GB 可用磁盘。Checkpoint、日志和视频不提交 Git。

开始前记录环境：

```bash
uname -a
lsb_release -a
nvidia-smi
git --version
python3 --version
df -h .
```

## 2. 同步 Synapse2Action

在已有 checkout 中执行：

```bash
cd /path/to/Synapse2Action
git status --short --branch
git fetch --prune origin
git pull --ff-only
```

工作区非空时不要强制覆盖。确认以下文件存在：

```bash
test -f simulation/whole_body.lock.json
test -x simulation/bootstrap_whole_body.sh
test -f simulation/check_whole_body_readiness.py
```

## 3. 拉取锁定源码

```bash
./simulation/bootstrap_whole_body.sh
```

脚本只会：

- 将 OpenWBT 拉到 `simulation/vendor/OpenWBT`；
- 将 OpenTrack 拉到 `simulation/vendor/OpenTrack`；
- Checkout `simulation/whole_body.lock.json` 中的精确 Commit；
- 校验实际 HEAD。

它不会安装依赖、下载模型、启动仿真或连接机器人。

随后检查：

```bash
python3 simulation/check_whole_body_readiness.py \
  --output reports/simulation/whole-body-readiness.json
```

预期结果为 `"ready": true`。这里的 Ready 只代表源码、入口、平台和 Commit 正确。

## 4. 路线 A：先跑 OpenTrack 部署 Smoke

OpenTrack 更适合先验证，因为它支持 headless、自动按键、日志和仿真/部署共用 C++ Controller。它验证的是动作跟踪与状态机，不是抓取任务。

### 4.0 Unitree 官方 locomotion 基线

OpenTrack 的 `STAND` 只做关节位置插值，不证明动态平衡；其随仓库提供的
`G1-Walk.onnx` 也没有携带可核验的训练配置。先运行锁定版本的 Unitree 官方
G1 policy 与匹配 MJCF，确认 MuJoCo、PyTorch 和基础行走环境正常：

```bash
simulation/vendor/OpenTrack/.venv/bin/python \
  simulation/run_unitree_locomotion_smoke.py \
  --duration 10 \
  --video reports/simulation/unitree-locomotion-smoke.mp4 \
  --output reports/simulation/unitree-locomotion-smoke.json
```

报告只有同时满足以下条件才通过：

- 所有状态均为有限数值；
- 5000 个 physics steps 内最低 root height 不低于 `0.65 m`；
- 默认前进指令产生至少 `1.0 m` 的位移；
- `unitree_rl_gym` 实际 commit 与 `whole_body.lock.json` 一致。

这个 Smoke 只验证下肢 locomotion 与动态平衡，不验证 OpenTrack 动作跟踪、
VLA、抓取、负载抬升或稳定放置。MP4 与 JSON 来自同一次 physics rollout。

### 4.0.1 Unitree 官方 29DoF velocity 基线

不要把上述 12DoF policy 直接套到 29DoF 模型。全身模型必须使用
`unitree_rl_lab` 随仓库发布的 480→29 ONNX、其 observation history、
`joint_ids_map`、PD 参数和 `unitree_mujoco` 匹配 MJCF：

```bash
python3 -m venv .venv
.venv/bin/pip install mujoco onnxruntime pyyaml imageio imageio-ffmpeg
.venv/bin/python simulation/run_unitree_29dof_velocity_smoke.py \
  --duration 10 --command-x 0.5 \
  --video reports/simulation/unitree-29dof-velocity-smoke.mp4 \
  --output reports/simulation/unitree-29dof-velocity-smoke.json
```

该基线验证 29DoF dynamic locomotion；它仍不是 VLA manipulation、抓取或
带负载 whole-body control 的成功证据。无视频运行适合数值验收；软件 EGL
较慢时，可用较短的同配置 rollout 单独生成视觉证据并保留各自 JSON。

### 4.1 安装训练/仿真 Python 环境

```bash
cd simulation/vendor/OpenTrack
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync -i https://pypi.org/simple
source .venv/bin/activate
```

如果 `uv sync` 报 CUDA/JAX 不匹配，停止并保存完整错误，不要随意升级依赖。上游锁定 Python `3.12.9`、JAX `0.4.38`、MuJoCo `3.3.1`。

初始化 MuJoCo 资源：

```bash
export GLI_PATH="$PWD"
export WANDB_PROJECT="synapse2action-opentrack"
export WANDB_ENTITY="disabled"
python track_mj/app/mj_playground_init.py
```

### 4.2 安装 C++ 部署依赖

```bash
sudo apt update
sudo apt install -y build-essential cmake libeigen3-dev libyaml-cpp-dev libgtest-dev unzip
```

按照 OpenTrack 上游 `deploy/README_deployment.md` 安装 ONNX Runtime、glog 与其打包的 Unitree SDK2 依赖。不要将依赖复制进 Synapse2Action 主 Python 环境。

### 4.3 准备公开 Checkpoint

从 OpenTrack README 指向的公开 Checkpoint 目录下载：

- 至少一个 Specialist；
- `general_tracker_lafan1_v2`；
- 对应动作的 `ref_data.onnx`；
- 保留上游 `storage/g1_tracking_constant.yaml`。

放置结构应满足：

```text
simulation/vendor/OpenTrack/deploy/storage/
├── data/<motion>/ref_data.onnx
├── policy/<policy>/checkpoints/
└── g1_tracking_constant.yaml
```

下载完成后记录文件 Hash：

```bash
find deploy/storage -type f -print0 | sort -z | xargs -0 sha256sum \
  > /tmp/opentrack-storage.sha256
```

### 4.4 构建 Controller

先构建不带 Torque Projection 的版本：

```bash
cd deploy
./build_wo_torque_projection.sh
```

构建失败时保留完整输出。不要先切换到真机网络接口。

### 4.5 启动 Headless MuJoCo

终端 A：

```bash
cd /path/to/Synapse2Action/simulation/vendor/OpenTrack/deploy/sim_interface
source ../../.venv/bin/activate
python main.py \
  --iface lo \
  --no-viewer \
  --auto-press "1000:R2,3000:A,5000:X,7000:SimStart" \
  --log-dir /tmp/s2a-opentrack-sim
```

终端 B：

```bash
cd /path/to/Synapse2Action/simulation/vendor/OpenTrack/deploy
./start_sim_wo_torque_projection.sh --iface lo
```

只允许 loopback `lo`。不要使用连接 G1 的物理网卡，也不要加入 `--allow-non-loopback`。

Smoke 通过至少应满足：

- Controller 进入 `DAMPING → STAND → LOCO`；
- 无 NaN、Inf 或进程异常退出；
- 生成 `mujoco_qpos_trace.csv`、Controller 日志和 `summary.txt`；
- `summary.txt` 的 `validation_result=PASS`。

然后可启动带 Viewer 的人工检查：

```bash
python main.py --iface lo --log-dir /tmp/s2a-opentrack-viewer
```

## 5. 路线 B：OpenWBT MuJoCo 遥操作

OpenWBT 当前 MuJoCo 入口会初始化 `TeleVisionWrapper`、Vision Pro/WebXR 数据和双臂 IK。没有 Vision Pro/兼容手部姿态源与 Joystick 时，不能把它当作自动抓取基线。

### 5.1 创建隔离环境

```bash
cd /path/to/Synapse2Action/simulation/vendor/OpenWBT
conda create -n s2a-openwbt python=3.8 -y
conda activate s2a-openwbt
conda install pinocchio=3.1.0 -c conda-forge -y
pip install meshcat casadi onnxruntime pyserial mujoco opencv-python
pip install -r requirements.txt
```

然后按上游 `installation.md` 安装 `unitree_sdk2_python`。OpenWBT 的 ROS 2 Foxy/CycloneDDS 配置只在真机通信或相应 ROS 路径需要；本次不得连接真实 G1。

### 5.2 检查模型与配置

```bash
test -f deploy/configs/run_loco_squat_grasp.yaml
test -f resources/robots/g1_description/g1_29dof_camera.xml
find ckpts -type f -maxdepth 3 -print
```

缺失 Checkpoint 时停止。不要用随机权重或固定轨迹冒充 OpenWBT。

### 5.3 启动仿真

在已经接入 Vision Pro/兼容姿态源和 Joystick 后执行：

```bash
python -m deploy.run_teleoperation_mujoco \
  --config run_loco_squat_grasp.yaml \
  --save_data \
  --save_data_dir /tmp/s2a-openwbt-data \
  --save_image
```

第一轮只验证站立、下蹲、双臂 IK 和停止。第二轮才加入物体抓取与抬升。运行过程中始终保留人工停止能力。

## 6. 抓取后抬升对照实验

Smoke 通过后，按 [`whole-body-lift-baseline.md`](whole-body-lift-baseline.md) 执行。必须保持：

- 与 GR00T 相同的 G1 模型、物体、初始姿态和 20 个 Seed；
- 从 Verifier 已确认的稳定抓取状态开始；
- 抬升门槛为物体相对起点超过 `0.10 m`；
- 分别记录抓取保持、最大高度、站立、Torque clipping、NaN/Inf 与停止原因；
- 不允许事后只挑成功 Seed。

目前上游 OpenTrack 的公开动作是人体动作跟踪，不包含现成 `lift_with_payload` 操作 Specialist。因此完成 OpenTrack Smoke 后，仍需制作负载抬升参考动作并训练 Specialist，不能把普通抬手动作计为物体抬升。

## 7. 回传证据

不要提交第三方 Checkpoint、Vendor 仓库、视频或大日志。将以下文件打包回传：

```bash
mkdir -p /tmp/s2a-whole-body-evidence
cp reports/simulation/whole-body-readiness.json /tmp/s2a-whole-body-evidence/
cp /tmp/opentrack-storage.sha256 /tmp/s2a-whole-body-evidence/ 2>/dev/null || true
cp -a /tmp/s2a-opentrack-sim /tmp/s2a-whole-body-evidence/ 2>/dev/null || true
cp -a /tmp/s2a-openwbt-data /tmp/s2a-whole-body-evidence/ 2>/dev/null || true
uname -a > /tmp/s2a-whole-body-evidence/uname.txt
nvidia-smi -q > /tmp/s2a-whole-body-evidence/nvidia-smi.txt
tar -C /tmp -czf /tmp/s2a-whole-body-evidence.tar.gz s2a-whole-body-evidence
sha256sum /tmp/s2a-whole-body-evidence.tar.gz
```

同时回传：

- 执行到哪一步；
- 第一条失败命令；
- 完整 stderr；
- `/tmp/s2a-whole-body-evidence.tar.gz`；
- 压缩包 SHA-256。

## 8. 禁止事项

- 不运行 OpenWBT/OpenTrack 的 Real/Deploy 真机入口。
- 不把 DDS 从 `lo` 切到物理网卡。
- 不使用 `sudo chmod -R 777`。
- 不因缺少模型而切回 Mock、随机 Policy 或固定抬升轨迹。
- 不把 Viewer 中“看起来正常”当作结果；以日志和物体状态为准。
- 不修改准入门槛来让候选通过。

本轮 Ubuntu 目标是得到可信的 Runtime Smoke 和失败证据，不是宣称系统已经解决全身操作。
