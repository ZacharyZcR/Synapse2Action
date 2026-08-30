from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.policy_admission import verify_policy_admission
from synapse2action.policy_evidence import (
    build_policy_evidence_bundle,
    verify_policy_evidence_bundle,
)
from tests.test_policy_admission import language_bundle, run, write_bundle


class PolicyEvidenceTests(unittest.TestCase):
    def build_bundle(
        self,
        root: Path,
        name: str,
        seeds: list[int],
        *,
        minimum_outcome_success_rate: float = 0.9,
    ) -> Path:
        inputs = root / f"{name}-inputs"
        inputs.mkdir()
        manifest, evaluation = language_bundle()
        run_paths, manifest_path, evaluation_path = write_bundle(
            str(inputs),
            [run(seed) for seed in seeds],
            manifest,
            evaluation,
        )
        admission = verify_policy_admission(
            run_paths,
            manifest_path,
            evaluation_path,
            required_seeds=seeds,
            minimum_outcome_success_rate=minimum_outcome_success_rate,
        )
        admission_path = inputs / "admission.json"
        admission_path.write_text(json.dumps(admission), encoding="utf-8")
        metadata_path = inputs / "release.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "policy_id": "fixture-policy",
                    "policy_version": name,
                    "model_sha256": "a" * 64,
                    "dataset_sha256": "b" * 64,
                    "controller_version": "controller-v1",
                    "code_revision": "0123456789abcdef",
                }
            ),
            encoding="utf-8",
        )
        output = root / name
        build_policy_evidence_bundle(
            output,
            run_paths=run_paths,
            language_manifest_path=manifest_path,
            language_evaluation_path=evaluation_path,
            admission_report_path=admission_path,
            release_metadata_path=metadata_path,
        )
        return output

    def test_valid_bundle_verifies(self) -> None:
        with TemporaryDirectory() as directory:
            bundle = self.build_bundle(Path(directory), "candidate", [1001, 1002])
            report = verify_policy_evidence_bundle(bundle)

        self.assertTrue(report["accepted"])
        self.assertEqual(report["failed_checks"], [])

    def test_mutated_run_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            bundle = self.build_bundle(Path(directory), "candidate", [1001])
            run_path = bundle / "runs" / "seed-1001.json"
            run_path.write_text(run_path.read_text() + " ", encoding="utf-8")
            report = verify_policy_evidence_bundle(bundle)

        self.assertFalse(report["accepted"])
        self.assertIn("hashes_valid", report["failed_checks"])

    def test_extra_file_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            bundle = self.build_bundle(Path(directory), "candidate", [1001])
            (bundle / "extra.txt").write_text("untracked", encoding="utf-8")
            report = verify_policy_evidence_bundle(bundle)

        self.assertFalse(report["accepted"])
        self.assertIn("files_complete", report["failed_checks"])

    def test_unsafe_manifest_path_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            bundle = self.build_bundle(Path(directory), "candidate", [1001])
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["path"] = "../outside.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = verify_policy_evidence_bundle(bundle)

        self.assertFalse(report["accepted"])
        self.assertIn("paths_safe", report["failed_checks"])

    def test_builder_never_overwrites_existing_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.build_bundle(root, "candidate", [1001])
            inputs = root / "candidate-inputs"
            with self.assertRaises(FileExistsError):
                build_policy_evidence_bundle(
                    bundle,
                    run_paths=[inputs / "run-0.json"],
                    language_manifest_path=inputs / "manifest.json",
                    language_evaluation_path=inputs / "evaluation.json",
                    admission_report_path=inputs / "admission.json",
                    release_metadata_path=inputs / "release.json",
                )

    def test_lowered_threshold_is_rejected_against_baseline(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.build_bundle(
                root, "baseline", [1001], minimum_outcome_success_rate=1.0
            )
            candidate = self.build_bundle(
                root, "candidate", [1001], minimum_outcome_success_rate=0.9
            )
            report = verify_policy_evidence_bundle(
                candidate, baseline_directory=baseline
            )

        self.assertFalse(report["accepted"])
        self.assertIn("outcome_threshold_not_lowered", report["failed_checks"])

    def test_reduced_seed_set_is_rejected_against_baseline(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.build_bundle(root, "baseline", [1001, 1002])
            candidate = self.build_bundle(root, "candidate", [1001])
            report = verify_policy_evidence_bundle(
                candidate, baseline_directory=baseline
            )

        self.assertFalse(report["accepted"])
        self.assertIn("required_seeds_not_reduced", report["failed_checks"])


if __name__ == "__main__":
    unittest.main()
