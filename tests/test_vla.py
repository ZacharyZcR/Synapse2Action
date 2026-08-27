from base64 import b64decode
import json
import unittest

from synapse2action.navigation import (
    BaseState,
    BaseVelocity,
    CameraFrame,
    NavigationObservation,
    NavigationTask,
    Pose2D,
    SensorFrame,
)
from synapse2action.vla import DeterministicVLABackend, VLANavigationPolicy, run_vla_navigation_demo


class StaticBackend:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def reset(self, task_payload: bytes) -> None:
        pass

    def infer(self, observation_payload: bytes) -> bytes:
        return json.dumps(self.response).encode()


def observation(task: NavigationTask) -> NavigationObservation:
    camera = CameraFrame(2, 2, "mono8", b"\x00\x01\x02\x03")
    sensor = SensorFrame(0, 0, Pose2D(0, 0), (), camera, BaseState())
    return NavigationObservation(sensor, task, 0)


class VLATests(unittest.TestCase):
    def test_vla_adapter_serializes_camera_and_completes_navigation(self) -> None:
        backend = DeterministicVLABackend()
        policy = VLANavigationPolicy(backend)

        report = run_vla_navigation_demo()

        self.assertTrue(report["passed"])
        self.assertEqual(report["navigation_policy"], "VLANavigationPolicy")
        self.assertEqual(report["policy_requests"], report["control_cycles"])
        self.assertEqual(report["serialized_observations"], report["control_cycles"])

        task = NavigationTask("navigate to point_b", Pose2D(1, 0))
        policy.reset(task)
        policy.predict(observation(task))
        camera = backend.requests[0]["sensor"]["camera"]
        self.assertEqual(b64decode(camera["data_base64"]), b"\x00\x01\x02\x03")

    def test_vla_adapter_rejects_extra_action_fields(self) -> None:
        backend = StaticBackend(
            {
                "schema_version": 1,
                "commands": [{"vx": 0.1, "vy": 0.0, "yaw_rate": 0.0, "duration_ms": 100, "joint": 7}],
            }
        )
        policy = VLANavigationPolicy(backend)
        task = NavigationTask("navigate", Pose2D(1, 0))
        policy.reset(task)

        with self.assertRaises(ValueError):
            policy.predict(observation(task))

    def test_vla_adapter_rejects_non_positive_duration(self) -> None:
        backend = StaticBackend(
            {
                "schema_version": 1,
                "commands": [{"vx": 0.1, "vy": 0.0, "yaw_rate": 0.0, "duration_ms": 0}],
            }
        )
        policy = VLANavigationPolicy(backend)
        task = NavigationTask("navigate", Pose2D(1, 0))
        policy.reset(task)

        with self.assertRaises(ValueError):
            policy.predict(observation(task))

    def test_vla_adapter_rejects_observation_for_another_task(self) -> None:
        policy = VLANavigationPolicy(DeterministicVLABackend())
        policy.reset(NavigationTask("navigate to b", Pose2D(1, 0)))

        with self.assertRaises(ValueError):
            policy.predict(observation(NavigationTask("navigate to c", Pose2D(2, 0))))

    def test_temporal_ensemble_blends_overlapping_chunk_predictions(self) -> None:
        backend = StaticBackend(
            {
                "schema_version": 1,
                "commands": [
                    {"vx": 1.0, "vy": 0.0, "yaw_rate": 0.0, "duration_ms": 100},
                    {"vx": 0.0, "vy": 0.0, "yaw_rate": 0.0, "duration_ms": 100},
                ],
            }
        )
        policy = VLANavigationPolicy(
            backend,
            execution_horizon=1,
            temporal_ensemble_decay=0.5,
        )
        task = NavigationTask("navigate", Pose2D(1, 0))
        policy.reset(task)

        first = policy.predict(observation(task))
        second = policy.predict(observation(task))

        self.assertEqual(first.commands, (BaseVelocity(1.0, 0.0, 0.0, 100),))
        self.assertAlmostEqual(second.commands[0].vx, 2 / 3)
        self.assertEqual(policy.max_ensemble_contributors, 2)
        self.assertEqual(policy.ensemble_reset_count, 0)


if __name__ == "__main__":
    unittest.main()
