import tempfile
import unittest
from pathlib import Path

from synapse2action.contracts import IntentKind
from synapse2action.eeg import FrequencyDecoder, SyntheticSSVEPSource, load_recording, save_recording


class EEGTests(unittest.TestCase):
    def test_four_ssvep_intents_decode_correctly(self) -> None:
        specs = [
            {"at_ms": index * 1000, "label": kind.value, "signal_amplitude": 1.0, "noise_std": 0.15}
            for index, kind in enumerate(IntentKind)
        ]
        windows = SyntheticSSVEPSource(seed=123).acquire(specs)
        decoder = FrequencyDecoder()

        decoded = [decoder.decode(window) for window in windows]

        self.assertEqual([result.kind for result in decoded if result], list(IntentKind))
        self.assertTrue(all(result and result.confidence >= 0.55 for result in decoded))

    def test_seeded_signal_is_deterministic(self) -> None:
        specs = [{"at_ms": 0, "label": "select", "signal_amplitude": 1.0, "noise_std": 0.2}]

        first = SyntheticSSVEPSource(seed=7).acquire(specs)
        second = SyntheticSSVEPSource(seed=7).acquire(specs)

        self.assertEqual(first, second)

    def test_recording_round_trip_preserves_samples(self) -> None:
        windows = SyntheticSSVEPSource(seed=9).acquire(
            [{"at_ms": 0, "label": "select", "signal_amplitude": 1.0, "noise_std": 0.2}]
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "recording.json"
            save_recording(path, windows)

            self.assertEqual(load_recording(path), windows)


if __name__ == "__main__":
    unittest.main()
