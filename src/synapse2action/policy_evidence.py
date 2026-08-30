from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Iterable, Mapping

from .policy_admission import file_digest


REQUIRED_METADATA = {
    "schema_version",
    "policy_id",
    "policy_version",
    "model_sha256",
    "dataset_sha256",
    "controller_version",
    "code_revision",
}


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence file must contain an object: {path}")
    return payload


def _validate_source(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"evidence source must be a regular non-symlink file: {path}")


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    if set(metadata) != REQUIRED_METADATA or metadata.get("schema_version") != 1:
        raise ValueError("release metadata has an invalid schema")
    for name in ("policy_id", "policy_version", "controller_version", "code_revision"):
        if not isinstance(metadata.get(name), str) or not metadata[name].strip():
            raise ValueError(f"release metadata requires {name}")
    for name in ("model_sha256", "dataset_sha256"):
        value = metadata.get(name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"release metadata requires lowercase {name}")


def _entry(role: str, relative: str, path: Path, **extra: object) -> dict[str, Any]:
    return {
        "role": role,
        "path": relative,
        "sha256": file_digest(path),
        "size_bytes": path.stat().st_size,
        **extra,
    }


def _bundle_digest(entries: Iterable[Mapping[str, Any]]) -> str:
    encoded = json.dumps(list(entries), sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def build_policy_evidence_bundle(
    output_directory: Path,
    *,
    run_paths: Iterable[Path],
    language_manifest_path: Path,
    language_evaluation_path: Path,
    admission_report_path: Path,
    release_metadata_path: Path,
) -> dict[str, Any]:
    if output_directory.exists():
        raise FileExistsError(f"evidence bundle already exists: {output_directory}")
    sources = [
        *list(run_paths),
        language_manifest_path,
        language_evaluation_path,
        admission_report_path,
        release_metadata_path,
    ]
    for source in sources:
        _validate_source(source)
    resolved = [source.resolve() for source in sources]
    if len(set(resolved)) != len(resolved):
        raise ValueError("evidence bundle sources must be unique")

    runs = [_load_object(path) for path in sources[:-4]]
    seeds = [run.get("seed") for run in runs]
    if not runs or not all(type(seed) is int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("evidence bundle runs require unique integer seeds")
    admission = _load_object(admission_report_path)
    metadata = _load_object(release_metadata_path)
    _validate_metadata(metadata)
    if admission.get("policy_id") != metadata["policy_id"]:
        raise ValueError("release metadata policy does not match admission report")
    expected_hashes = admission.get("evidence_sha256")
    if not isinstance(expected_hashes, dict):
        raise ValueError("admission report does not bind source evidence hashes")
    if expected_hashes.get("runs") != [file_digest(path) for path in sources[:-4]]:
        raise ValueError("run evidence changed after admission")
    if expected_hashes.get("language_manifest") != file_digest(language_manifest_path):
        raise ValueError("language manifest changed after admission")
    if expected_hashes.get("language_evaluation") != file_digest(language_evaluation_path):
        raise ValueError("language evaluation changed after admission")
    if set(seeds) != set(admission.get("observed_seeds", [])):
        raise ValueError("bundle seeds do not match admission report")

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_directory.name}-", dir=output_directory.parent)
    )
    try:
        targets = {
            "admission": temporary / "admission.json",
            "language_manifest": temporary / "language" / "qualification.json",
            "language_evaluation": temporary / "language" / "evaluation.json",
            "release_metadata": temporary / "metadata" / "release.json",
        }
        for target in targets.values():
            target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(admission_report_path, targets["admission"])
        shutil.copyfile(language_manifest_path, targets["language_manifest"])
        shutil.copyfile(language_evaluation_path, targets["language_evaluation"])
        shutil.copyfile(release_metadata_path, targets["release_metadata"])
        entries = [
            _entry("admission", "admission.json", targets["admission"]),
            _entry(
                "language_manifest",
                "language/qualification.json",
                targets["language_manifest"],
            ),
            _entry(
                "language_evaluation",
                "language/evaluation.json",
                targets["language_evaluation"],
            ),
            _entry(
                "release_metadata",
                "metadata/release.json",
                targets["release_metadata"],
            ),
        ]
        for index, (source, seed) in enumerate(zip(sources[:-4], seeds, strict=True)):
            relative = f"runs/seed-{seed}.json"
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            entries.append(_entry("run", relative, target, admission_index=index, seed=seed))
        entries.sort(key=lambda item: item["path"])
        manifest = {
            "schema_version": 1,
            "format": "synapse2action.policy_evidence_bundle",
            "policy_id": metadata["policy_id"],
            "files": entries,
            "bundle_digest": _bundle_digest(entries),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        if output_directory.exists():
            raise FileExistsError(f"evidence bundle appeared during build: {output_directory}")
        temporary.replace(output_directory)
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _safe_relative_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return None
    return path


def _inspect_bundle(directory: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, bool]]:
    manifest_path = directory / "manifest.json"
    manifest = _load_object(manifest_path)
    entries = manifest.get("files")
    checks = {
        "manifest_schema_valid": bool(
            manifest.get("schema_version") == 1
            and manifest.get("format") == "synapse2action.policy_evidence_bundle"
            and isinstance(entries, list)
        ),
        "paths_safe": True,
        "files_complete": True,
        "hashes_valid": True,
        "bundle_digest_valid": False,
        "roles_complete": False,
        "admission_binding_valid": False,
        "metadata_valid": False,
    }
    if not isinstance(entries, list):
        return manifest, {}, checks
    expected_paths = {"manifest.json"}
    roles = []
    run_entries = []
    seen_paths = set()
    for entry in entries:
        if not isinstance(entry, dict):
            checks["paths_safe"] = False
            checks["hashes_valid"] = False
            continue
        relative = _safe_relative_path(entry.get("path"))
        if relative is None or str(relative) in seen_paths:
            checks["paths_safe"] = False
            continue
        seen_paths.add(str(relative))
        expected_paths.add(str(relative))
        path = directory.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file():
            checks["files_complete"] = False
            continue
        if (
            file_digest(path) != entry.get("sha256")
            or path.stat().st_size != entry.get("size_bytes")
        ):
            checks["hashes_valid"] = False
        role = entry.get("role")
        roles.append(role)
        if role == "run":
            run_entries.append(entry)
    actual_paths = {
        str(path.relative_to(directory).as_posix())
        for path in directory.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    checks["files_complete"] = checks["files_complete"] and actual_paths == expected_paths
    checks["bundle_digest_valid"] = manifest.get("bundle_digest") == _bundle_digest(entries)
    checks["roles_complete"] = bool(
        roles.count("admission") == 1
        and roles.count("language_manifest") == 1
        and roles.count("language_evaluation") == 1
        and roles.count("release_metadata") == 1
        and bool(run_entries)
        and roles.count("run") == len(run_entries)
    )
    try:
        admission = _load_object(directory / "admission.json")
        metadata = _load_object(directory / "metadata" / "release.json")
        _validate_metadata(metadata)
        checks["metadata_valid"] = metadata.get("policy_id") == manifest.get("policy_id")
        run_metadata_valid = bool(
            all(type(entry.get("admission_index")) is int for entry in run_entries)
            and all(type(entry.get("seed")) is int for entry in run_entries)
            and {entry.get("admission_index") for entry in run_entries}
            == set(range(len(run_entries)))
        )
        run_entries.sort(
            key=lambda item: (
                item.get("admission_index")
                if type(item.get("admission_index")) is int
                else -1
            )
        )
        evidence_hashes = admission.get("evidence_sha256", {})
        checks["admission_binding_valid"] = bool(
            run_metadata_valid
            and isinstance(evidence_hashes, dict)
            and admission.get("policy_id") == manifest.get("policy_id")
            and evidence_hashes.get("runs") == [entry.get("sha256") for entry in run_entries]
            and evidence_hashes.get("language_manifest")
            == file_digest(directory / "language" / "qualification.json")
            and evidence_hashes.get("language_evaluation")
            == file_digest(directory / "language" / "evaluation.json")
            and set(admission.get("observed_seeds", []))
            == {entry.get("seed") for entry in run_entries}
        )
    except (OSError, ValueError, TypeError):
        admission = {}
    return manifest, admission, checks


def verify_policy_evidence_bundle(
    directory: Path,
    *,
    baseline_directory: Path | None = None,
) -> dict[str, Any]:
    manifest, admission, checks = _inspect_bundle(directory)
    checks["admission_accepted"] = admission.get("accepted") is True
    regression = {
        "baseline_integrity_valid": True,
        "policy_line_consistent": True,
        "outcome_threshold_not_lowered": True,
        "required_seeds_not_reduced": True,
    }
    if baseline_directory is not None:
        baseline_manifest, baseline_admission, baseline_checks = _inspect_bundle(
            baseline_directory
        )
        regression["baseline_integrity_valid"] = bool(
            all(baseline_checks.values()) and baseline_admission.get("accepted") is True
        )
        regression["policy_line_consistent"] = (
            manifest.get("policy_id") == baseline_manifest.get("policy_id")
        )
        current_acceptance = admission.get("acceptance")
        baseline_acceptance = baseline_admission.get("acceptance")
        current_threshold = (
            current_acceptance.get("minimum_outcome_success_rate")
            if isinstance(current_acceptance, dict)
            else None
        )
        baseline_threshold = (
            baseline_acceptance.get("minimum_outcome_success_rate")
            if isinstance(baseline_acceptance, dict)
            else None
        )
        regression["outcome_threshold_not_lowered"] = bool(
            isinstance(current_threshold, (int, float))
            and isinstance(baseline_threshold, (int, float))
            and current_threshold >= baseline_threshold
        )
        current_seeds = admission.get("required_seeds", [])
        baseline_seeds = baseline_admission.get("required_seeds", [])
        regression["required_seeds_not_reduced"] = bool(
            all(type(seed) is int for seed in current_seeds)
            and all(type(seed) is int for seed in baseline_seeds)
            and set(current_seeds) >= set(baseline_seeds)
        )
    accepted = all(checks.values()) and all(regression.values())
    return {
        "schema_version": 1,
        "verification": "policy_evidence_bundle",
        "accepted": accepted,
        "bundle_digest": manifest.get("bundle_digest"),
        "checks": checks,
        "regression": regression,
        "failed_checks": [
            name
            for name, passed in {**checks, **regression}.items()
            if not passed
        ],
    }
