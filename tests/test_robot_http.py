import json
import socket
import unittest

from synapse2action.navigation import BaseVelocity, DEFAULT_NAVIGATION_SCENARIO, Pose2D
from synapse2action.robot_http import EmbeddedRobotServer, HTTPRobotTransport
from synapse2action.robot_transport import (
    LoopbackRobotTransport,
    decode_command_receipt,
    decode_sensor_packet,
    encode_base_command,
    encode_observation_request,
)
from synapse2action.vla import run_vla_navigation_demo


class RobotHTTPTests(unittest.TestCase):
    def test_http_transport_preserves_robot_wire_payloads(self) -> None:
        bridge = LoopbackRobotTransport(Pose2D(0.0, 0.0))
        captured = []

        def http_transport(url, headers, payload, timeout):
            captured.append((url, headers, json.loads(payload), timeout))
            if url.endswith("/exchange"):
                return bridge.exchange(payload)
            if url.endswith("/halt"):
                bridge.halt()
            else:
                bridge.stop()
            return b'{"ok":true}'

        transport = HTTPRobotTransport(
            "http://localhost:9100/v1/",
            api_key="secret",
            timeout_seconds=2.5,
            transport=http_transport,
        )
        sensor = decode_sensor_packet(
            transport.exchange(encode_observation_request(0, 0)),
            0,
        )
        receipt = decode_command_receipt(
            transport.exchange(
                encode_base_command(0, BaseVelocity(0.5, 0.0, 0.0, 100), 0)
            ),
            0,
        )
        transport.halt()

        self.assertEqual(sensor.frame.frame_id, 0)
        self.assertTrue(receipt.accepted)
        self.assertEqual(
            [request[0] for request in captured],
            [
                "http://localhost:9100/v1/exchange",
                "http://localhost:9100/v1/exchange",
                "http://localhost:9100/v1/halt",
            ],
        )
        self.assertTrue(all(request[1]["Authorization"] == "Bearer secret" for request in captured))
        self.assertTrue(all(request[3] == 2.5 for request in captured))
        self.assertEqual(transport.observation_request_count, 1)
        self.assertEqual(transport.command_request_count, 1)
        self.assertEqual(transport.halt_count, 1)

    def test_embedded_bridge_runs_full_vla_loop_over_real_http(self) -> None:
        scenario = DEFAULT_NAVIGATION_SCENARIO
        bridge = LoopbackRobotTransport(
            scenario.start,
            scenario.obstacles,
            robot_radius_m=scenario.robot_radius_m,
            sensor_range_m=scenario.sensor_range_m,
        )
        with EmbeddedRobotServer(bridge) as server:
            port = server.port
            transport = HTTPRobotTransport(server.base_url)
            report = run_vla_navigation_demo(
                scenario=scenario,
                transport=transport,
            )

            self.assertTrue(report["passed"])
            self.assertEqual(report["robot_transport"], "http")
            self.assertEqual(report["transport_observations"], 45)
            self.assertEqual(report["transport_commands"], 44)
            self.assertEqual(report["transport_halts"], 1)
            self.assertEqual(len(server.requests), 90)
            exchange_payloads = [
                request.payload for request in server.requests if request.operation == "exchange"
            ]
            self.assertEqual(
                sum(payload["operation"] == "observe" for payload in exchange_payloads),
                45,
            )
            self.assertEqual(
                sum(payload["operation"] == "base_velocity" for payload in exchange_payloads),
                44,
            )
            self.assertEqual(server.requests[-1].operation, "halt")
            self.assertEqual(bridge.halt_count, 1)
            transport.close()

        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.1)


if __name__ == "__main__":
    unittest.main()
