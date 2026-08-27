import json
import unittest

from synapse2action.llm_planner import OpenAICompatiblePlanner
from synapse2action.demo import run_demo


class LLMPlannerTests(unittest.TestCase):
    def test_structured_plan_is_converted_to_action(self) -> None:
        captured = {}

        def transport(url, headers, payload, timeout):
            captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "skill": "pick_and_place",
                                    "arguments": {"target": "red_cube", "destination": "drop_zone"},
                                }
                            )
                        }
                    }
                ]
            }

        planner = OpenAICompatiblePlanner(
            "http://localhost:8000/v1", "test-model", api_key="test-key", transport=transport
        )

        action = planner.plan("red_cube")

        self.assertEqual(action.skill, "pick_and_place")
        self.assertEqual(action.arguments["target"], "red_cube")
        self.assertEqual(captured["url"], "http://localhost:8000/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertTrue(captured["payload"]["response_format"]["json_schema"]["strict"])

    def test_invalid_response_is_rejected(self) -> None:
        planner = OpenAICompatiblePlanner(
            "http://localhost:8000/v1",
            "test-model",
            transport=lambda *_: {"choices": [{"message": {"content": "not json"}}]},
        )

        with self.assertRaises(ValueError):
            planner.plan("red_cube")

    def test_adapter_runs_complete_hardware_free_pipeline(self) -> None:
        planner = OpenAICompatiblePlanner(
            "http://localhost:8000/v1",
            "test-model",
            transport=lambda *_: {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "skill": "pick_and_place",
                                    "arguments": {"target": "red_cube", "destination": "drop_zone"},
                                }
                            )
                        }
                    }
                ]
            },
        )

        report = run_demo(planner=planner)

        self.assertTrue(report["passed"])
        self.assertEqual(report["pipeline"][3], "OpenAICompatiblePlanner")
        self.assertEqual(report["robot_actions"], 1)


if __name__ == "__main__":
    unittest.main()
