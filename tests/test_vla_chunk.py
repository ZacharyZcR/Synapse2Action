import json
import unittest

from synapse2action.vla_chunk import (
    G1ActionChunk,
    G1ActionChunkPlayer,
    G1ChunkCoordinator,
    G1ChunkRuntimeMetrics,
    OpenPIChunkClient,
    SmolVLAChunkClient,
    parse_g1_action_chunk,
    validate_g1_action_chunk_motion,
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
    def test_motion_validator_accepts_bounded_chunk(self) -> None:
        chunk = G1ActionChunk(
            "run",
            0,
            tuple(tuple(0.1 * step if index == 12 else 0.0 for index in range(29)) for step in (1, 2)),
            1.0,
        )

        validate_g1_action_chunk_motion(
            chunk,
            initial_position_rad=[0.0] * 29,
            initial_velocity_rad_s=[0.0] * 29,
            joint_indices=[12],
            joint_limits_rad=[(-1.0, 1.0)],
            frequency_hz=10.0,
            maximum_velocity_rad_s=2.0,
            maximum_acceleration_rad_s2=20.0,
            maximum_duration_s=0.2,
        )

    def test_motion_validator_rejects_every_configured_limit(self) -> None:
        def chunk(*values: float) -> G1ActionChunk:
            return G1ActionChunk(
                "run",
                0,
                tuple(tuple(value if index == 12 else 0.0 for index in range(29)) for value in values),
                1.0,
            )

        common = {
            "initial_position_rad": [0.0] * 29,
            "initial_velocity_rad_s": [0.0] * 29,
            "joint_indices": [12],
            "joint_limits_rad": [(-1.0, 1.0)],
            "frequency_hz": 10.0,
            "maximum_velocity_rad_s": 100.0,
            "maximum_acceleration_rad_s2": 1000.0,
            "maximum_duration_s": 1.0,
        }
        cases = (
            ("position", chunk(1.1), {}),
            ("velocity", chunk(0.3), {"maximum_velocity_rad_s": 2.0}),
            (
                "acceleration",
                chunk(0.1, 0.3),
                {
                    "initial_velocity_rad_s": [0.0] * 12 + [1.0] + [0.0] * 16,
                    "maximum_acceleration_rad_s2": 5.0,
                },
            ),
            ("duration", chunk(0.0, 0.0, 0.0), {"maximum_duration_s": 0.2}),
        )
        for label, action_chunk, overrides in cases:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, label):
                validate_g1_action_chunk_motion(
                    action_chunk,
                    **(common | overrides),
                )

    def test_openpi_requires_explicit_observation_and_embodiment_mapping(self) -> None:
        class Policy:
            def __init__(self) -> None:
                self.observations = []
                self.resets = 0

            def reset(self) -> None:
                self.resets += 1

            def infer(self, observation):
                self.observations.append(observation)
                return {
                    "actions": [[1.0, 2.0], [3.0, 4.0]],
                    "server_timing": {"infer_ms": 7.5},
                }

        policy = Policy()
        client = OpenPIChunkClient(
            policy,
            observation_encoder=lambda task, state, images: {
                "prompt": task,
                "observation/state": tuple(state),
                "camera_names": tuple(sorted(images)),
            },
            action_mapper=lambda action: [*action, *([0.0] * 27)],
        )
        images = {"base": b"rgb", "wrist": b"rgb"}

        chunk = client.infer(
            session_id="run",
            sequence=0,
            task="pick the apple",
            state=[0.0] * 29,
            images=images,
        )

        self.assertEqual(policy.resets, 1)
        self.assertEqual(policy.observations[0]["prompt"], "pick the apple")
        self.assertEqual(chunk.actions[0][:2], (1.0, 2.0))
        self.assertEqual(len(chunk.actions[0]), 29)
        self.assertEqual(chunk.inference_ms, 7.5)

    def test_openpi_rejects_unmapped_or_unbounded_actions(self) -> None:
        class Policy:
            def reset(self) -> None:
                pass

            def infer(self, observation):
                return {"actions": [[1.0, 2.0]]}

        client = OpenPIChunkClient(
            Policy(),
            observation_encoder=lambda task, state, images: {},
            action_mapper=lambda action: action,
        )
        with self.assertRaisesRegex(ValueError, "29"):
            client.infer(
                session_id="run",
                sequence=0,
                task="pick",
                state=[0.0] * 29,
                images={},
            )

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
        self.assertEqual(metrics.report()["first_chunk_round_trip_ms"], 4800)
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
