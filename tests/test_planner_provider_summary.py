from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.planner_provider_summary import summarize_planner_providers


def provider_report(model: str, accepted: bool = True, provider: str = "test") -> dict:
    return {
        "schema_version": 2,
        "benchmark": "live_planner_provider",
        "provider": provider,
        "model": model,
        "output_mode": "json-schema",
        "accepted": accepted,
        "passed": 6 if accepted else 5,
        "failed": 0 if accepted else 1,
        "metrics": {
            "schema_compliance_rate": 1.0,
            "unsafe_action_executions": 0,
            "provider_errors": 0,
            "latency_ms_p95": 1200.0,
        },
        "acceptance": {},
        "results": [],
    }


class PlannerProviderSummaryTests(unittest.TestCase):
    def test_summary_requires_every_named_model_to_pass(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            deepseek = root / "deepseek.json"
            qwen = root / "qwen.json"
            deepseek.write_text(json.dumps(provider_report("deepseek")))
            qwen.write_text(json.dumps(provider_report("qwen")))

            report = summarize_planner_providers(
                [qwen, deepseek],
                ["test/deepseek", "test/qwen", "test/glm"],
            )

        self.assertFalse(report["accepted"])
        self.assertEqual(report["missing_models"], ["test/glm"])
        self.assertEqual([item["model"] for item in report["providers"]], ["deepseek", "qwen"])
        self.assertTrue(all(len(item["sha256"]) == 64 for item in report["providers"]))

    def test_rejected_provider_prevents_acceptance(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "glm.json"
            path.write_text(json.dumps(provider_report("glm", accepted=False)))

            report = summarize_planner_providers([path], ["test/glm"])

        self.assertFalse(report["accepted"])
        self.assertEqual(report["rejected_models"], ["test/glm"])

    def test_duplicate_models_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / "one.json", Path(directory) / "two.json"]
            for path in paths:
                path.write_text(json.dumps(provider_report("same-model")))

            with self.assertRaisesRegex(ValueError, "unique identities"):
                summarize_planner_providers(paths)


if __name__ == "__main__":
    unittest.main()
