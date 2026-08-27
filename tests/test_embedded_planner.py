import socket
import unittest

from synapse2action.demo import run_demo
from synapse2action.embedded_planner import EmbeddedPlannerServer
from synapse2action.llm_planner import OpenAICompatiblePlanner


class EmbeddedPlannerTests(unittest.TestCase):
    def test_real_http_round_trip_completes_pipeline(self) -> None:
        with EmbeddedPlannerServer("red_cube", "drop_zone") as server:
            port = server.port
            planner = OpenAICompatiblePlanner(server.base_url, "embedded-planner")

            report = run_demo(planner=planner)

            self.assertTrue(report["passed"])
            self.assertEqual(len(server.requests), 1)
            self.assertEqual(server.requests[0]["model"], "embedded-planner")
            self.assertEqual(report["robot_actions"], 1)

        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.1)


if __name__ == "__main__":
    unittest.main()
