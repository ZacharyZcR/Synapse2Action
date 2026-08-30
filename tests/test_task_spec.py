from pathlib import Path
import unittest

from synapse2action.task_spec import load_task_spec
from synapse2action.language_qualification import build_language_qualification


ROOT = Path(__file__).resolve().parents[1]


class TaskSpecTests(unittest.TestCase):
    def test_task_spec_is_the_single_task_contract(self) -> None:
        task = load_task_spec(ROOT / "experiments/tasks/g1_pick_place.json")

        self.assertEqual(task.arguments, {
            "target": task.target_entity.name,
            "destination": task.destination_entity.name,
        })
        task.validate_action(task.skill, task.arguments)
        self.assertEqual(len(task.controller.joint_indices), len(task.controller.joint_limits_rad))
        self.assertEqual(task.controller.maximum_chunk_velocity_rad_s, 2.0)
        self.assertEqual(task.controller.maximum_chunk_acceleration_rad_s2, 20.0)
        self.assertEqual(task.controller.maximum_chunk_duration_s, 20.0)
        self.assertIn(task.target, task.action_text())
        self.assertIn(task.target, task.planner_instruction)
        self.assertIn(task.destination, task.planner_instruction)
        self.assertNotEqual(task.instruction, task.counterfactual_instruction)

    def test_mismatched_action_is_rejected(self) -> None:
        task = load_task_spec(ROOT / "experiments/tasks/g1_pick_place.json")

        with self.assertRaisesRegex(ValueError, "does not match"):
            task.validate_action(task.skill, {"target": "different", "destination": task.destination})

    def test_language_suite_covers_three_distinct_tasks_and_decisions(self) -> None:
        tasks = [load_task_spec(path) for path in sorted((ROOT / "experiments/tasks").glob("*.json"))]

        report = build_language_qualification(tasks)

        self.assertEqual(len(report["task_specs"]), 3)
        self.assertEqual(report["case_count"], 18)
        decisions = {case["expected_decision"] for case in report["cases"]}
        self.assertEqual(decisions, {"execute", "change_behavior", "refuse"})
        for task in tasks:
            canonical = next(
                case
                for case in report["cases"]
                if case["case_id"] == f"{task.task_id}:canonical"
            )
            self.assertEqual(canonical["expected_arguments"], task.arguments)


if __name__ == "__main__":
    unittest.main()
