#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import gymnasium as gym
import numpy as np

from gr00t.eval import rollout_policy


ENV_NAME = "gr00tlocomanip_g1_sim/LMPnPAppleToPlateDC_G1_gear_wbc"
MIN_GRASP_STEPS = 10


def longest_true_run(values: list[bool]) -> tuple[int | None, int]:
    best_start = None
    best_length = 0
    current_start = 0
    current_length = 0
    for index, value in enumerate(values):
        if not value:
            current_length = 0
            continue
        if current_length == 0:
            current_start = index
        current_length += 1
        if current_length > best_length:
            best_start = current_start
            best_length = current_length
    return best_start, best_length


class EvidenceWrapper(gym.Wrapper):
    def __init__(self, env: gym.Env, output: Path, minimum_lift_m: float, seed: int) -> None:
        super().__init__(env)
        self.output = output
        self.minimum_lift_m = minimum_lift_m
        self.seed = seed
        self.episodes: list[dict[str, object]] = []
        self.samples: list[dict[str, object]] = []
        self.initial_apple_z: float | None = None

    @property
    def scene(self):
        return self.env.unwrapped.base_env

    def reset(self, **kwargs):
        self._finish_episode()
        seed = kwargs.get("seed")
        if seed is None:
            seed = self.seed + len(self.episodes)
            kwargs["seed"] = seed
        scene = self.scene
        scene.seed = seed
        scene.rng = np.random.default_rng(seed)
        if hasattr(scene, "scene"):
            scene.scene._scene_sampler = scene.scene._get_sampler()
        observation, info = self.env.reset(**kwargs)
        self.initial_apple_z = self._body_position(self.scene.apple)[2]
        self._sample()
        return observation, info

    def step(self, action):
        result = self.env.step(action)
        self._sample()
        return result

    def close(self) -> None:
        self._finish_episode()
        self._write()
        super().close()

    def _body_position(self, obj) -> np.ndarray:
        body_id = self.scene.obj_body_id[obj.mj_obj.name]
        return self.scene.sim.data.body_xpos[body_id].copy()

    def _sample(self) -> None:
        scene = self.scene
        apple_pos = self._body_position(scene.apple)
        plate_pos = self._body_position(scene.plate)
        robot = scene.robots[0]
        robot_pos = scene.sim.data.get_body_xpos(robot.robot_model.root_body).copy()
        grasped = any(
            scene._check_grasp(robot.gripper[side], scene.apple.mj_obj)
            for side in ("left", "right")
        )
        torso_id = scene.sim.model.body_name2id("robot0_torso_link")
        torso_pos = scene.sim.data.body_xpos[torso_id]
        torso_up = scene.sim.data.body_xmat[torso_id].reshape(3, 3)[2, 2]
        self.samples.append(
            {
                "apple_position": apple_pos.tolist(),
                "plate_position": plate_pos.tolist(),
                "robot_position": robot_pos.tolist(),
                "grasped": bool(grasped),
                "contact": bool(scene.check_contact(scene.apple.mj_obj, scene.plate.mj_obj)),
                "standing": bool(torso_pos[2] > 0.55 and torso_up > 0.7),
            }
        )

    def _finish_episode(self) -> None:
        if len(self.samples) <= 1 or self.initial_apple_z is None:
            self.samples = []
            self.initial_apple_z = None
            return
        grasp_flags = [bool(sample["grasped"]) for sample in self.samples]
        grasp_index, grasp_steps = longest_true_run(grasp_flags)
        grasp_end_index = None if grasp_index is None else grasp_index + grasp_steps - 1
        sustained_grasp = grasp_steps >= MIN_GRASP_STEPS
        lifts = [
            float(sample["apple_position"][2]) - self.initial_apple_z
            for sample in self.samples
        ]
        peak_lift_step = int(np.argmax(lifts))
        max_lift_m = lifts[peak_lift_step]
        apple_plate_distances = [
            float(
                np.linalg.norm(
                    np.array(sample["apple_position"][:2])
                    - np.array(sample["plate_position"][:2])
                )
            )
            for sample in self.samples
        ]
        robot_plate_distances = [
            float(
                np.linalg.norm(
                    np.array(sample["robot_position"][:2])
                    - np.array(sample["plate_position"][:2])
                )
            )
            for sample in self.samples
        ]
        closest_plate_step = int(np.argmin(apple_plate_distances))
        contact_index = None
        if sustained_grasp and grasp_index is not None:
            contact_index = next(
                (
                    index
                    for index in range(grasp_index, len(self.samples))
                    if self.samples[index]["contact"]
                ),
                None,
            )
        released_index = None
        if contact_index is not None:
            released_index = next(
                (
                    index
                    for index in range(contact_index + 1, len(self.samples))
                    if not self.samples[index]["grasped"]
                ),
                None,
            )
        settled = False
        if released_index is not None and len(self.samples) - released_index >= 10:
            tail = self.samples[-10:]
            positions = np.array([sample["apple_position"] for sample in tail])
            settled = bool(
                all(sample["contact"] for sample in tail)
                and np.max(np.linalg.norm(positions - positions[-1], axis=1)) < 0.01
            )
        self.episodes.append(
            {
                "steps": len(self.samples),
                "seed": self.seed + len(self.episodes),
                "gripper_contact": any(grasp_flags),
                "maximum_consecutive_grasp_steps": grasp_steps,
                "sustained_grasp_start_step": grasp_index,
                "sustained_grasp_end_step": grasp_end_index,
                "grasped": sustained_grasp,
                "maximum_lift_m": max_lift_m,
                "peak_lift_step": peak_lift_step,
                "initial_apple_plate_xy_distance_m": apple_plate_distances[0],
                "minimum_apple_plate_xy_distance_m": min(apple_plate_distances),
                "closest_plate_step": closest_plate_step,
                "final_apple_plate_xy_distance_m": apple_plate_distances[-1],
                "apple_plate_progress_m": apple_plate_distances[0] - min(apple_plate_distances),
                "initial_robot_plate_xy_distance_m": robot_plate_distances[0],
                "minimum_robot_plate_xy_distance_m": min(robot_plate_distances),
                "final_robot_plate_xy_distance_m": robot_plate_distances[-1],
                "lifted": sustained_grasp and grasp_index is not None and any(
                    sample["apple_position"][2] > self.initial_apple_z + self.minimum_lift_m
                    for sample in self.samples[grasp_index:]
                ),
                "contacted_plate": any(sample["contact"] for sample in self.samples),
                "contacted_plate_after_grasp": contact_index is not None,
                "released_after_contact": released_index is not None,
                "stable_on_plate": settled,
                "remained_standing": all(sample["standing"] for sample in self.samples),
            }
        )
        self.samples = []
        self.initial_apple_z = None
        self._write()

    def _write(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps({"episodes": self.episodes}, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-episode-steps", type=int, default=1440)
    parser.add_argument("--minimum-lift-m", type=float, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--policy-client-host", default="127.0.0.1")
    parser.add_argument("--policy-client-port", type=int, default=5555)
    args = parser.parse_args()

    original_get_gym_env = rollout_policy.get_gym_env

    def instrumented_env(env_name: str, env_idx: int, total_n_envs: int):
        env = original_get_gym_env(env_name, env_idx, total_n_envs)
        return EvidenceWrapper(env, args.output, args.minimum_lift_m, args.seed)

    rollout_policy.get_gym_env = instrumented_env
    config = rollout_policy.WrapperConfigs(
        video=rollout_policy.VideoConfig(
            video_dir=str(args.output.parent / "groot-evidence-video"),
            max_episode_steps=args.max_episode_steps,
        ),
        multistep=rollout_policy.MultiStepConfig(
            n_action_steps=20,
            max_episode_steps=args.max_episode_steps,
            terminate_on_success=False,
        ),
    )
    policy = rollout_policy.create_gr00t_sim_policy(
        "",
        rollout_policy.get_embodiment_tag_from_env_name(ENV_NAME),
        args.policy_client_host,
        args.policy_client_port,
    )
    result = rollout_policy.run_rollout_gymnasium_policy(
        env_name=ENV_NAME,
        policy=policy,
        wrapper_configs=config,
        n_episodes=1,
        n_envs=1,
    )
    print("results:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
