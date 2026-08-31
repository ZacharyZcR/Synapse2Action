from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Callable

from .task_spec import TaskSpec
from .policy_evidence import verify_policy_evidence_bundle


@dataclass(frozen=True, slots=True)
class PolicyManifest:
    policy_id: str
    backend: str
    release: str
    embodiment: str
    task_ids: tuple[str, ...]
    skills: tuple[str, ...]
    state_dimension: int
    cameras: tuple[str, ...]
    action_dimension: int
    action_representation: str
    control_frequency_hz: float
    qualification: str
    evidence_bundle: str | None
    evidence_sha256: str | None

    @property
    def admitted(self) -> bool:
        return self.qualification == "admitted"

    def supports(self, task: TaskSpec, embodiment: str) -> bool:
        return bool(
            self.embodiment == embodiment
            and task.task_id in self.task_ids
            and task.skill in self.skills
        )


def load_policy_manifest(path: Path) -> PolicyManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "policy_id", "backend", "release", "embodiment",
        "capabilities", "observation", "action", "admission",
    }
    if not isinstance(raw, dict) or set(raw) != expected or raw.get("schema_version") != 1:
        raise ValueError(f"invalid policy manifest schema: {path}")
    capabilities = raw["capabilities"]
    observation = raw["observation"]
    action = raw["action"]
    admission = raw["admission"]
    if not all(isinstance(item, dict) for item in (capabilities, observation, action, admission)):
        raise ValueError(f"invalid policy manifest sections: {path}")
    if (
        set(capabilities) != {"task_ids", "skills"}
        or set(observation) != {"state_dimension", "cameras"}
        or set(action) != {"dimension", "representation", "control_frequency_hz"}
        or set(admission) != {"status", "evidence_bundle", "evidence_sha256"}
        or not isinstance(capabilities["task_ids"], list)
        or not isinstance(capabilities["skills"], list)
        or not isinstance(observation["cameras"], list)
        or type(observation["state_dimension"]) is not int
        or type(action["dimension"]) is not int
        or type(action["control_frequency_hz"]) not in {int, float}
        or any(
            not isinstance(raw[key], str)
            for key in ("policy_id", "backend", "release", "embodiment")
        )
        or not isinstance(action["representation"], str)
        or not isinstance(admission["status"], str)
        or any(not isinstance(value, str) for value in capabilities["task_ids"])
        or any(not isinstance(value, str) for value in capabilities["skills"])
        or any(not isinstance(value, str) for value in observation["cameras"])
    ):
        raise ValueError(f"invalid policy manifest contract: {path}")
    manifest = PolicyManifest(
        policy_id=str(raw["policy_id"]),
        backend=str(raw["backend"]),
        release=str(raw["release"]),
        embodiment=str(raw["embodiment"]),
        task_ids=tuple(str(value) for value in capabilities.get("task_ids", ())),
        skills=tuple(str(value) for value in capabilities.get("skills", ())),
        state_dimension=observation["state_dimension"],
        cameras=tuple(str(value) for value in observation["cameras"]),
        action_dimension=action["dimension"],
        action_representation=str(action["representation"]),
        control_frequency_hz=float(action["control_frequency_hz"]),
        qualification=str(admission["status"]),
        evidence_bundle=admission.get("evidence_bundle"),
        evidence_sha256=admission.get("evidence_sha256"),
    )
    scalar_strings = (
        manifest.policy_id, manifest.backend, manifest.release, manifest.embodiment,
        manifest.action_representation,
    )
    if (
        any(not value for value in scalar_strings)
        or not manifest.task_ids
        or not manifest.skills
        or len(set(manifest.task_ids)) != len(manifest.task_ids)
        or len(set(manifest.skills)) != len(manifest.skills)
        or not manifest.cameras
        or len(set(manifest.cameras)) != len(manifest.cameras)
        or manifest.state_dimension <= 0
        or manifest.action_dimension <= 0
        or manifest.control_frequency_hz <= 0
        or manifest.qualification not in {"candidate", "admitted", "retired"}
    ):
        raise ValueError(f"incomplete policy manifest: {path}")
    evidence = (manifest.evidence_bundle, manifest.evidence_sha256)
    if manifest.admitted and (
        not all(isinstance(value, str) and value for value in evidence)
        or len(manifest.evidence_sha256 or "") != 64
        or any(character not in "0123456789abcdef" for character in manifest.evidence_sha256 or "")
    ):
        raise ValueError(f"admitted policy lacks immutable evidence: {path}")
    if not manifest.admitted and any(value is not None for value in evidence):
        raise ValueError(f"unadmitted policy must not claim evidence: {path}")
    return manifest


class PolicyRegistry:
    def __init__(self, manifests: tuple[PolicyManifest, ...]) -> None:
        ids = [manifest.policy_id for manifest in manifests]
        if not manifests or len(ids) != len(set(ids)):
            raise ValueError("policy registry requires unique manifests")
        self._manifests = {manifest.policy_id: manifest for manifest in manifests}

    @classmethod
    def load(cls, directory: Path) -> PolicyRegistry:
        paths = sorted(directory.glob("*.json"))
        if not paths:
            raise ValueError(f"policy registry is empty: {directory}")
        manifests = tuple(load_policy_manifest(path) for path in paths)
        for manifest in manifests:
            if not manifest.admitted:
                continue
            relative = PurePosixPath(manifest.evidence_bundle or "")
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise ValueError(f"unsafe policy evidence path: {manifest.policy_id}")
            report = verify_policy_evidence_bundle(
                directory.parent.joinpath(*relative.parts)
            )
            if (
                report.get("accepted") is not True
                or report.get("bundle_digest") != manifest.evidence_sha256
            ):
                raise ValueError(f"policy evidence is invalid: {manifest.policy_id}")
        return cls(manifests)

    def select(
        self,
        task: TaskSpec,
        *,
        embodiment: str,
        requested_policy: str = "auto",
        allow_candidate: bool = False,
    ) -> PolicyManifest:
        eligible = [
            manifest for manifest in self._manifests.values()
            if manifest.supports(task, embodiment)
            and (manifest.admitted or allow_candidate and manifest.qualification == "candidate")
        ]
        if requested_policy != "auto":
            eligible = [item for item in eligible if item.policy_id == requested_policy]
        if not eligible:
            raise ValueError("no admitted policy supports the requested task and embodiment")
        if len(eligible) != 1:
            raise ValueError("policy selection is ambiguous; request an exact policy id")
        return eligible[0]


class PolicyLifecycle:
    def __init__(
        self,
        *,
        safe_stop: Callable[[], None],
        clear_action_buffer: Callable[[], None],
        reset_observation_history: Callable[[], None],
    ) -> None:
        self._safe_stop = safe_stop
        self._clear_action_buffer = clear_action_buffer
        self._reset_observation_history = reset_observation_history
        self.active_policy: str | None = None
        self.executing = False

    def activate(self, policy_id: str) -> None:
        if not policy_id:
            raise ValueError("policy id must not be empty")
        if self.executing:
            raise RuntimeError("cannot switch policy during execution")
        if self.active_policy == policy_id:
            return
        if self.active_policy is not None:
            self._safe_stop()
        self._clear_action_buffer()
        self._reset_observation_history()
        self.active_policy = policy_id

    def begin(self) -> None:
        if self.active_policy is None:
            raise RuntimeError("cannot execute without an active policy")
        self.executing = True

    def finish(self) -> None:
        self.executing = False
