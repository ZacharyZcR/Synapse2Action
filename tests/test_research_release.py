from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from synapse2action.research_release import (
    build_research_release,
    verify_research_release,
)


ROOT = Path(__file__).resolve().parents[1]


class ResearchReleaseTests(unittest.TestCase):
    def test_checked_manifest_matches_release_files(self) -> None:
        report = verify_research_release(
            ROOT,
            ROOT / "research/release-source.json",
            ROOT / "research/release-v1.json",
        )
        self.assertTrue(report["accepted"], report["detail"])

    def test_manifest_contains_only_tracked_files(self) -> None:
        manifest = json.loads((ROOT / "research/release-v1.json").read_text())
        paths = [item["path"] for item in manifest["files"]]
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", *paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unpublished_directories_are_not_manifest_files(self) -> None:
        manifest = json.loads((ROOT / "research/release-v1.json").read_text())
        paths = [item["path"] for item in manifest["files"]]
        excluded = [item["path"] for item in manifest["unpublished_assets"]]
        self.assertFalse(
            [path for path in paths if any(path.startswith(prefix) for prefix in excluded)]
        )

    def test_verification_rejects_modified_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/card.md").write_text("first\n")
            source = {
                "schema_version": 1,
                "release_id": "fixture-v1",
                "collections": [{"name": "cards", "patterns": ["docs/*.md"]}],
                "unpublished_assets": [],
            }
            source_path = root / "source.json"
            manifest_path = root / "manifest.json"
            source_path.write_text(json.dumps(source))
            manifest_path.write_text(json.dumps(build_research_release(root, source_path)))
            (root / "docs/card.md").write_text("second\n")
            report = verify_research_release(root, source_path, manifest_path)
            self.assertFalse(report["accepted"])

    def test_builder_rejects_unsafe_or_empty_collections(self) -> None:
        for patterns in (["../secret"], ["missing/*.md"]):
            with self.subTest(patterns=patterns), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source_path = root / "source.json"
                source_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "release_id": "fixture-v1",
                            "collections": [{"name": "cards", "patterns": patterns}],
                            "unpublished_assets": [],
                        }
                    )
                )
                with self.assertRaises(ValueError):
                    build_research_release(root, source_path)


if __name__ == "__main__":
    unittest.main()
