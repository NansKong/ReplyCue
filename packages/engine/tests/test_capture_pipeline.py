"""Exercise capture -> transcription -> question -> answer without real audio or APIs."""
import audioop
import struct
import threading
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import QApplication, Studio
from PySide6.QtTest import QTest
APP = QApplication.instance() or QApplication([])

class Stream:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def is_active(self): return True

class NoiseStream(Stream):
    def __init__(self, callback):
        self.callback = callback
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.produce)
    def produce(self):
        while not self.stop.wait(.05):
            self.callback(struct.pack('<h', 1000) * 1600, 800, {}, 0)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(1)

class Audio:
    selected = None
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get_default_wasapi_loopback(self):
        raise AssertionError('Explicit source must be used instead of the default')
    def get_device_info_by_index(self, index):
        Audio.selected = index
        return {'index': index, 'name': 'Synthetic meeting output', 'maxInputChannels': 2,
                'defaultSampleRate': 16000, 'isLoopbackDevice': True}
    def open(self, **options):
        # Speech below the previous RMS threshold; no silent callbacks follow it.
        options['stream_callback'](struct.pack('<h', 100) * 19200, 9600, {}, 0)
        return Stream()

class NoisyAudio(Audio):
    def open(self, **options):
        super().open(**options)
        return NoiseStream(options['stream_callback'])

class Cleaner:
    def __init__(self, rate, channels):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def feed(self, data):
        from groq_backend import prepare_audio
        import io, wave
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(data)
        with wave.open(io.BytesIO(prepare_audio(output.getvalue()))) as wav:
            return [(wav.readframes(wav.getnframes()), audioop.rms(data, 2) < 500)]

class CapturePipelineTests(unittest.TestCase):
    def test_quiet_question_reaches_answer_with_explicit_source(self):
        self.exercise(Audio)

    def test_continuous_background_noise_does_not_delay_the_answer(self):
        self.exercise(NoisyAudio)

    def exercise(self, audio_class):
        studio = Studio()
        studio.live = True
        studio.documents = {}
        studio.audio_device_index = 42
        fake = types.SimpleNamespace(PyAudio=audio_class, paInt16=8, paContinue=0)
        try:
            with patch.dict(sys.modules, {'pyaudiowpatch': fake}), patch('noise_filter.SpeechCleaner', Cleaner), \
                 patch('groq_backend.transcribe', return_value='What is computer vision?') as transcribe, \
                 patch('groq_backend.generate_answer', side_effect=OSError), \
                 patch('replicate_backend.ReplicateBackend.predict', return_value=['Computer vision interprets images.']) as predict:
                studio.start_capture()
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline and not studio.session_memory:
                    APP.processEvents()
                    QTest.qWait(10)
                self.assertEqual(Audio.selected, 42)
                transcribe.assert_called_once()
                predict.assert_called_once()
                self.assertEqual(studio.history, ['What is computer vision?'])
                self.assertEqual(studio.qa_records[0]['status'], 'Complete')
                self.assertIn('Computer vision interprets images.', studio.panel.live_text)
        finally:
            studio.live = False
            studio.cancel_pending()
            for worker in studio.workers(): worker.wait(2000)
            studio.close()
            APP.processEvents()

if __name__ == '__main__': unittest.main()
