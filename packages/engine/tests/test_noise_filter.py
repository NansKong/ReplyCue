import audioop
import random
import sys
import unittest
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from noise_filter import SpeechCleaner


class NoiseFilterTests(unittest.TestCase):
    def test_steady_noise_is_reduced_without_becoming_continuous_speech(self):
        rng = random.Random(42)
        samples = array('h', (round(rng.gauss(0, 300)) for _ in range(72000)))
        with SpeechCleaner(48000, 1) as cleaner:
            frames = cleaner.feed(samples.tobytes())
        output = b''.join(pcm for pcm, _ in frames)
        self.assertEqual(len(output), 48000)
        self.assertLess(audioop.rms(output[16000:], 2), audioop.rms(samples.tobytes(), 2) * .25)
        self.assertLess(sum(speech for _, speech in frames), 25)

    def test_stereo_resampling_matches_for_whole_and_fragmented_callbacks(self):
        rng = random.Random(7)
        samples = array('h', (rng.randint(-400, 400) for _ in range(44100 * 2)))
        with SpeechCleaner(44100, 2) as cleaner:
            whole = cleaner.feed(samples.tobytes())
        with SpeechCleaner(44100, 2) as cleaner:
            fragmented = []
            for index in range(0, len(samples), 514):
                fragmented.extend(cleaner.feed(samples[index:index + 514].tobytes()))
        self.assertEqual(whole, fragmented)
        self.assertGreater(sum(len(pcm) for pcm, _ in whole), 31000)

    def test_stopped_callbacks_release_the_partial_frame_once(self):
        with SpeechCleaner(48000, 1) as cleaner:
            self.assertEqual(cleaner.feed(b'\\0' * 320), [])
            tail = cleaner.flush()
            self.assertEqual(sum(len(pcm) for pcm, _ in tail), 640)
            self.assertEqual(cleaner.flush(), [])

    def test_noise_filter_releases_native_state_and_rejects_use_after_close(self):
        cleaner = SpeechCleaner(48000, 1)
        cleaner.close()
        cleaner.close()
        self.assertIsNone(cleaner.state)
        with self.assertRaises(ValueError):
            cleaner.feed(b'\0' * 960)


if __name__ == '__main__':
    unittest.main()
