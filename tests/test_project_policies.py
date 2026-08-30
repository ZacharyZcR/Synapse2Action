from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectPolicyTests(unittest.TestCase):
    def test_versioned_manifest_resolves_every_policy(self) -> None:
        manifest = json.loads((ROOT / "docs/policy-manifest.json").read_text())

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            set(manifest["documents"]),
            {"contribution", "governance", "privacy", "responsible_use", "security"},
        )
        for relative in manifest["documents"].values():
            path = ROOT / relative
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())

    def test_policy_set_covers_project_safety_invariants(self) -> None:
        manifest = json.loads((ROOT / "docs/policy-manifest.json").read_text())
        controls = set(manifest["required_controls"])
        self.assertEqual(
            controls,
            {
                "capability_claim_scope",
                "confidential_vulnerability_reporting",
                "human_data_consent",
                "model_output_has_no_safety_authority",
                "physical_operation_requires_human_override",
                "reproducible_evidence",
            },
        )

        security = (ROOT / "SECURITY.md").read_text()
        privacy = (ROOT / "PRIVACY.md").read_text()
        responsible = (ROOT / "RESPONSIBLE_USE.md").read_text()
        governance = (ROOT / "GOVERNANCE.md").read_text()
        contributing = (ROOT / "CONTRIBUTING.md").read_text()
        self.assertIn("private vulnerability-reporting", security)
        self.assertIn("LLM/VLA output never owns emergency stop", security)
        self.assertIn("ethics/IRB approval and explicit informed consent", privacy)
        self.assertIn("Human override always", responsible)
        self.assertIn("MuJoCo is not", governance)
        self.assertIn("physical-G1 evidence", governance)
        self.assertIn("exact model, data, controller, code revision", contributing.replace("\n", " "))

    def test_readme_links_every_governing_policy(self) -> None:
        readme = (ROOT / "README.md").read_text()
        for name in (
            "CONTRIBUTING.md",
            "GOVERNANCE.md",
            "SECURITY.md",
            "PRIVACY.md",
            "RESPONSIBLE_USE.md",
        ):
            self.assertIn(f"]({name})", readme)


if __name__ == "__main__":
    unittest.main()
