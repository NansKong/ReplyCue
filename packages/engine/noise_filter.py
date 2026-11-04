"""Streaming local RNNoise suppression and speech detection for playback PCM."""
import audioop
import ctypes
from array import array
from pathlib import Path


class SpeechCleaner:
    frame_samples = 480
    processing_rate = 48000
    output_rate = 16000

    def __init__(self, rate, channels):
        if rate <= 0 or channels <= 0:
            raise ValueError('Invalid audio format')
        self.rate, self.channels = rate, channels
        self.input_state = self.output_state = None
        self.pending = bytearray()
        self.voice_hold = 0
        self.library = ctypes.CDLL(str(Path(__file__).resolve().parent / 'assets' / 'rnnoise' / 'rnnoise.dll'))
        self.library.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.library.rnnoise_create.restype = ctypes.c_void_p
        self.library.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.library.rnnoise_destroy.restype = None
        self.library.rnnoise_process_frame.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
        self.library.rnnoise_process_frame.restype = ctypes.c_float
        self.state = self.library.rnnoise_create(None)
        if not self.state:
            raise MemoryError('Could not initialize noise suppression')
        self.frame = (ctypes.c_float * self.frame_samples)()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.state:
            self.library.rnnoise_destroy(self.state)
            self.state = None
        self.pending.clear()

    def feed(self, data):
        if not self.state:
            raise ValueError('Noise filter is closed')
        if not data:
            return []
        if len(data) % (2 * self.channels):
            raise ValueError('Incomplete PCM frame')
        if self.channels == 2:
            data = audioop.tomono(data, 2, 0.5, 0.5)
        elif self.channels > 2:
            samples = array('h', data)
            data = array('h', (round(sum(samples[offset:offset + self.channels]) / self.channels)
                              for offset in range(0, len(samples), self.channels))).tobytes()
        if self.rate != self.processing_rate:
            data, self.input_state = audioop.ratecv(
                data, 2, 1, self.rate, self.processing_rate, self.input_state)
        self.pending.extend(data)
        output = []
        frame_bytes = self.frame_samples * 2
        while len(self.pending) >= frame_bytes:
            pcm = bytes(self.pending[:frame_bytes])
            del self.pending[:frame_bytes]
            self.frame[:] = array('h', pcm)
            probability = self.library.rnnoise_process_frame(self.state, self.frame, self.frame)
            if probability >= 0.5:
                self.voice_hold = 12
            else:
                self.voice_hold = max(0, self.voice_hold - 1)
            # Keep short unvoiced consonants alongside a detected word.
            speech = self.voice_hold > 0
            cleaned = array('h', (int(max(-32768, min(32767, value))) for value in self.frame)).tobytes()
            cleaned, self.output_state = audioop.ratecv(
                cleaned, 2, 1, self.processing_rate, self.output_rate, self.output_state)
            output.append((cleaned, speech))
        return output
