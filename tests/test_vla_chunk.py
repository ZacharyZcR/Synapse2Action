import json
import unittest

from synapse2action.vla_chunk import (
    G1ActionChunk,
    G1ActionChunkPlayer,
    G1ChunkCoordinator,
    G1ChunkRuntimeMetrics,
    SmolVLAChunkClient,
    parse_g1_action_chunk,
)


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
            self.assertEqual(payload["image_encoding"], "rgb8-256x256")
            self.assertEqual(timeout, 30.0)
            return Response({"session_id": "run", "sequence": 3, "actions": [[0.0] * 29] * 50, "inference_ms": 12.5})

        client = SmolVLAChunkClient("http://policy", opener=open_request)
        result = client.infer(
            session_id="run", sequence=3, task="pick", state=[0.0] * 29,
            images={name: bytes(256 * 256 * 3) for name in ("camera1", "camera2", "camera3")},
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

    def test_chunk_player_consumes_at_ten_hz_and_expires(self) -> None:
        actions = tuple((float(index),) * 29 for index in range(50))
        player = G1ActionChunkPlayer(frequency_hz=10, stale_after_s=7)
        player.load(G1ActionChunk("run", 0, actions, 1.0), now_s=5.0)
        self.assertEqual(player.current(now_s=5.49), actions[4])
        self.assertFalse(player.needs_refresh(now_s=9.4))
        self.assertTrue(player.needs_refresh(now_s=9.5))
        self.assertEqual(player.current(now_s=10.5), actions[-1])
        self.assertIsNone(player.current(now_s=12.01))

    def test_chunk_player_rejects_old_or_cross_session_chunk(self) -> None:
        action = ((0.0,) * 29,)
        player = G1ActionChunkPlayer()
        player.load(G1ActionChunk("run", 2, action, 1.0), now_s=0.0)
        for chunk in (G1ActionChunk("run", 2, action, 1.0), G1ActionChunk("other", 3, action, 1.0)):
            with self.assertRaisesRegex(ValueError, "ordered"):
                player.load(chunk, now_s=1.0)

    def test_runtime_gate_separates_functional_and_realtime_results(self) -> None:
        action = ((0.0,) * 29,) * 50
        metrics = G1ChunkRuntimeMetrics()
        metrics.record_chunk(G1ActionChunk("run", 0, action, 4500, 4800))
        self.assertTrue(metrics.report()["accepted"])
        metrics.record_chunk(G1ActionChunk("run", 1, action, 6100, 6400))
        metrics.record_stale_fallback()
        report = metrics.report()
        self.assertFalse(report["accepted"])
        self.assertFalse(report["checks"]["latency_within_chunk_coverage"])
        self.assertEqual(report["stale_fallbacks"], 1)

    def test_coordinator_keeps_one_ordered_request_in_flight(self) -> None:
        class Client:
            def infer(self, **request: object) -> G1ActionChunk:
                sequence = int(request["sequence"])
                return G1ActionChunk("run", sequence, ((float(sequence),) * 29,), 1.0, 2.0)

        coordinator = G1ChunkCoordinator(Client(), session_id="run", task="pick")
        images = {name: bytes(256 * 256 * 3) for name in ("camera1", "camera2", "camera3")}
        self.assertTrue(coordinator.request([0.0] * 29, images, request_overhead_ms=3.0))
        self.assertFalse(coordinator.request([0.0] * 29, images))
        first = coordinator.poll(timeout_s=1)
        self.assertEqual(first.sequence, 0)
        self.assertEqual(first.round_trip_ms, 5.0)
        self.assertTrue(coordinator.request([0.0] * 29, images))
        second = coordinator.poll(timeout_s=1)
        self.assertEqual(second.sequence, 1)
        self.assertEqual(coordinator.metrics.report()["chunks_received"], 2)
        coordinator.close()


if __name__ == "__main__":
    unittest.main()
