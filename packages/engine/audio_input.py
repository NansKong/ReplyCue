"""PCM turn boundaries, including WASAPI streams that stop callbacks in silence."""
import audioop
import io
import wave
from collections import deque


def playback_sources():
    import pyaudiowpatch as pa
    with pa.PyAudio() as audio:
        return [{'index': int(device['index']), 'name': device['name']}
                for device in audio.get_loopback_device_info_generator()]


class TurnBuffer:
    def __init__(self, rate, channels, threshold=60, silence_seconds=.45):
        self.rate, self.channels, self.threshold = rate, channels, threshold
        self.silence_seconds = silence_seconds
        self.active = False
        self.preroll = deque()
        self.pending = []
        self.duration = self.voiced = self.silence = 0.0
        self.last_frame = None
        self.level = 0

    def feed(self, data, now, speech=None):
        duration = len(data) / (2 * self.channels * self.rate)
        self.level = audioop.rms(data, 2) if data else 0
        active = self.level >= self.threshold if speech is None else speech
        self.active = active
        self.last_frame = now
        if active and not self.pending:
            self.pending = [pcm for pcm, _, _ in self.preroll]
            self.duration = sum(seconds for _, seconds, _ in self.preroll)
            self.voiced = sum(seconds for _, seconds, voiced in self.preroll if voiced)
            self.preroll.clear()
        if active or self.pending:
            self.pending.append(data)
            self.duration += duration
            self.voiced += duration if active else 0
            self.silence = 0 if active else self.silence + duration
            if self.silence >= self.silence_seconds:
                return self.flush()
            if self.duration >= 3:
                # A short overlap preserves words that cross an upload boundary.
                overlap_bytes = round(self.rate * .25) * self.channels * 2
                overlap = b''.join(self.pending)[-overlap_bytes:]
                output = self.flush()
                self.preroll.clear()
                self.preroll.append((overlap, len(overlap) / (2 * self.channels * self.rate), True))
                return output
        else:
            self.preroll.append((data, duration, False))
            while sum(seconds for _, seconds, _ in self.preroll) > .15:
                self.preroll.popleft()
        return None

    def idle(self, now):
        # Some output endpoints deliver no silent buffers after playback ends.
        # Count that gap as silence, rather than waiting forever for another callback.
        if self.pending and self.last_frame is not None and self.silence + now - self.last_frame >= self.silence_seconds:
            return self.flush()
        return None

    def flush(self):
        result = None
        if self.voiced >= .25:
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                wav.setnchannels(self.channels)
                wav.setsampwidth(2)
                wav.setframerate(self.rate)
                wav.writeframes(b''.join(self.pending))
            result = output.getvalue()
        self.pending = []
        self.duration = self.voiced = self.silence = 0.0
        return result
