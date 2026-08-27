import json
import socket
import unittest

from synapse2action.vla import run_vla_navigation_demo
from synapse2action.vla_http import EmbeddedVLAServer, HTTPVLABackend


class VLAHTTPTests(unittest.TestCase):
    def test_http_backend_sends_reset_and_infer_payloads(self) -> None:
        captured = []

        def transport(url, headers, payload, timeout):
            captured.append((url, headers, json.loads(payload), timeout))
            if url.endswith("/reset"):
                return b'{"ok":true}'
            return b'{"schema_version":1,"commands":[{"vx":0.1,"vy":0.0,"yaw_rate":0.0,"duration_ms":100}]}'

        backend = HTTPVLABackend(
            "http://localhost:9000/v1/",
            api_key="secret",
            timeout_seconds=2.5,
            transport=transport,
        )
        backend.reset(b'{"schema_version":1,"task":{}}')
        response = backend.infer(b'{"schema_version":1,"sensor":{}}')

        self.assertEqual([item[0] for item in captured], [
            "http://localhost:9000/v1/reset",
            "http://localhost:9000/v1/infer",
        ])
        self.assertEqual(captured[0][1]["Authorization"], "Bearer secret")
        self.assertEqual(captured[0][3], 2.5)
        self.assertEqual(json.loads(response)["schema_version"], 1)
        self.assertEqual(backend.request_count, 2)

    def test_embedded_vla_real_http_round_trip_and_shutdown(self) -> None:
        with EmbeddedVLAServer() as server:
            port = server.port
            report = run_vla_navigation_demo(HTTPVLABackend(server.base_url))

            self.assertTrue(report["passed"])
            self.assertEqual(report["vla_backend"], "HTTPVLABackend")
            self.assertEqual(len(server.requests), report["control_cycles"] + 1)
            self.assertEqual(report["policy_backend_requests"], report["control_cycles"] + 1)
            self.assertIsNone(report["replan_count"])
            self.assertEqual(server.requests[0].operation, "reset")
            self.assertTrue(all(request.operation == "infer" for request in server.requests[1:]))

        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.1)


if __name__ == "__main__":
    unittest.main()
