import io
import struct
import sys
import unittest
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_input import TurnBuffer

def pcm(level, seconds, channels=1, rate=16000):
    return struct.pack('<h', level) * round(seconds * rate * channels)

class AudioTurnTests(unittest.TestCase):
    def test_quiet_speech_flushes_when_callbacks_stop(self):
        buffer = TurnBuffer(16000, 1)
        self.assertIsNone(buffer.feed(pcm(100, .6), 1))
        self.assertIsNone(buffer.idle(1.4))
        output = buffer.idle(1.46)
        self.assertIsNotNone(output)
        with wave.open(io.BytesIO(output)) as wav:
            self.assertEqual(wav.getnframes(), 9600)
        self.assertIsNone(buffer.idle(2))

    def test_callback_sizes_use_actual_sample_count(self):
        buffer = TurnBuffer(16000, 2)
        buffer.feed(pcm(500, .4, 2), .4)
        output = buffer.feed(pcm(0, .46, 2), .86)
        with wave.open(io.BytesIO(output)) as wav:
            self.assertEqual(wav.getnchannels(), 2)
            self.assertEqual(wav.getnframes(), 13760)

    def test_partial_silence_and_missing_callbacks_count_together(self):
        buffer = TurnBuffer(16000, 1)
        buffer.feed(pcm(500, .6), 1)
        buffer.feed(pcm(0, .25), 1.25)
        self.assertIsNotNone(buffer.idle(1.46))

    def test_silence_and_click_do_not_create_transcription_requests(self):
        buffer = TurnBuffer(16000, 1)
        for i in range(20):
            self.assertIsNone(buffer.feed(pcm(0, .1), i * .1))
        buffer.feed(pcm(2000, .02), 2)
        self.assertIsNone(buffer.idle(3))

    def test_consecutive_questions_do_not_merge_across_silence(self):
        buffer = TurnBuffer(16000, 1)
        buffer.feed(pcm(500, .4), .4)
        first = buffer.idle(1)
        buffer.feed(pcm(800, .5), 2)
        second = buffer.idle(2.5)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first, second)

    def test_continuous_speech_uploads_early_with_an_overlap(self):
        buffer = TurnBuffer(16000, 1)
        for index in range(29):
            self.assertIsNone(buffer.feed(pcm(500, .1), index * .1))
        first = buffer.feed(pcm(500, .1), 2.9)
        self.assertIsNotNone(first)
        self.assertIsNone(buffer.feed(pcm(500, .1), 3.0))
        second = buffer.idle(3.5)
        with wave.open(io.BytesIO(first)) as wav:
            self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), 3.0)
        with wave.open(io.BytesIO(second)) as wav:
            self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), .35)

if __name__ == '__main__': unittest.main()
