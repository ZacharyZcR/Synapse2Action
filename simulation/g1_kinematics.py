from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD


ARM_JOINTS = {
    "left": (
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
    ),
    "right": (
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
    ),
}


def solve_hand_position(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    side: str,
    target: np.ndarray,
    *,
    iterations: int = 200,
) -> tuple[float, ...]:
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"{side}_wrist_yaw_link")
    joints = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in ARM_JOINTS[side]]
    dofs = np.array([model.jnt_dofadr[joint] for joint in joints])
    qpos = np.array([model.jnt_qposadr[joint] for joint in joints])
    jacobian = np.zeros((3, model.nv))
    rotational = np.zeros((3, model.nv))
    for _ in range(iterations):
        mujoco.mj_forward(model, data)
        error = target - data.xpos[body_id]
        if np.linalg.norm(error) < 0.002:
            break
        mujoco.mj_jacBody(model, data, jacobian, rotational, body_id)
        step = np.linalg.pinv(jacobian[:, dofs], rcond=1e-3) @ error
        data.qpos[qpos] += np.clip(step, -0.05, 0.05)
        for joint, address in zip(joints, qpos, strict=True):
            data.qpos[address] = np.clip(data.qpos[address], *model.jnt_range[joint])
    mujoco.mj_forward(model, data)
    error = float(np.linalg.norm(target - data.xpos[body_id]))
    if error >= 0.01:
        raise RuntimeError(
            f"{side} hand target is unreachable: achieved={data.xpos[body_id].tolist()}, error={error:.4f}"
        )
    return tuple(float(data.qpos[address]) for address in qpos)


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve a G1 rubber-hand position from official geometry")
    parser.add_argument("model", type=Path)
    parser.add_argument("side", choices=("left", "right"))
    parser.add_argument("x", type=float)
    parser.add_argument("y", type=float)
    parser.add_argument("z", type=float)
    args = parser.parse_args()
    model = mujoco.MjModel.from_xml_path(str(args.model))
    data = mujoco.MjData(model)
    data.qpos[2] = 0.78
    data.qpos[7 : 7 + len(G1_FIX_STAND_POSITION_RAD)] = G1_FIX_STAND_POSITION_RAD
    values = solve_hand_position(model, data, args.side, np.array((args.x, args.y, args.z)))
    print(json.dumps({"side": args.side, "joint_position_rad": values}))


if __name__ == "__main__":
    main()
