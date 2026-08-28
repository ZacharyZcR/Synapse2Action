import json
import unittest

from synapse2action.vla_chunk import SmolVLAChunkClient, parse_g1_action_chunk


class Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class VLAChunkTests(unittest.TestCase):
    def test_client_serializes_three_images_and_validates_chunk(self) -> None:
        def open_request(request: object, *, timeout: float) -> Response:
            payload = json.loads(request.data)
            self.assertEqual(set(payload["images"]), {"camera1", "camera2", "camera3"})
            self.assertEqual(timeout, 30.0)
            return Response({"session_id": "run", "sequence": 3, "actions": [[0.0] * 29] * 50, "inference_ms": 12.5})

        client = SmolVLAChunkClient("http://policy", opener=open_request)
        result = client.infer(
            session_id="run", sequence=3, task="pick", state=[0.0] * 29,
            images={name: b"image" for name in ("camera1", "camera2", "camera3")},
        )
        self.assertEqual(len(result.actions), 50)

    def test_parser_rejects_stale_and_malformed_actions(self) -> None:
        valid = {"session_id": "run", "sequence": 1, "actions": [[0.0] * 29], "inference_ms": 1.0}
        with self.assertRaisesRegex(ValueError, "stale"):
            parse_g1_action_chunk(valid, session_id="run", sequence=2)
        valid["sequence"] = 2
        valid["actions"] = [[0.0] * 28]
        with self.assertRaisesRegex(ValueError, "29"):
            parse_g1_action_chunk(valid, session_id="run", sequence=2)


if __name__ == "__main__":
    unittest.main()
