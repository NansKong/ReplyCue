"""In-memory Groq transcription; no fallback or automatic retries."""
import json
import managed_ai
import io
import wave
import audioop
import uuid
import urllib.request
import urllib.error

class TranscriptionError(Exception):
    pass


def generate_answer(key, prompt, coding=False):
    payload = {
        'model': 'openai/gpt-oss-20b' if coding else 'llama-3.1-8b-instant',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_completion_tokens': 4096 if coding else 256,
        'temperature': 0.3,
    }
    if coding:
        payload['reasoning_effort'] = 'low'
    request = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=7 if coding else 4) as response:
        choice = json.load(response)['choices'][0]
    if choice['finish_reason'] != 'stop' or not choice['message'].get('content'):
        raise ValueError('Incomplete answer')
    return choice['message']['content'].strip()


def prepare_audio(audio):
    """Send compact 16 kHz mono PCM, preserving the original if it isn't WAV."""
    if not audio.startswith(b'RIFF'):
        return audio
    try:
        with wave.open(io.BytesIO(audio), 'rb') as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            pcm = source.readframes(source.getnframes())
        if width != 2 or channels not in (1, 2):
            return audio
        if channels == 2:
            pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
        if rate != 16000:
            pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
        out = io.BytesIO()
        with wave.open(out, 'wb') as target:
            target.setnchannels(1); target.setsampwidth(2); target.setframerate(16000); target.writeframes(pcm)
        return out.getvalue()
    except (wave.Error, EOFError, ValueError):
        return audio


def transcribe(audio, key, model='whisper-large-v3-turbo', interrupted=lambda: False):
    if interrupted():
        return ''
    if managed_ai.enabled():
        try:
            return managed_ai.transcribe(prepare_audio(audio))
        except ValueError as error:
            raise TranscriptionError(str(error)) from None
    if not key:
        raise TranscriptionError('Set GROQ_API_KEY in .env and restart the app.')
    if not audio or len(audio) > 24*1024*1024:
        raise TranscriptionError('Audio turn is empty or exceeds the upload limit.')
    audio = prepare_audio(audio)
    boundary = '----Teleprompter'+uuid.uuid4().hex
    parts = []
    for name,value in [('model', model), ('response_format','json'), ('temperature','0')]:
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="turn.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode())
    parts.extend([audio, f'\r\n--{boundary}--\r\n'.encode()])
    request = urllib.request.Request('https://api.groq.com/openai/v1/audio/transcriptions',
        data=b''.join(parts), headers={'Authorization':'Bearer '+key, 'User-Agent':'InterviewCopilot/0.1',
        'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
        if interrupted():
            return ''
        text = result.get('text')
        if not isinstance(text,str):
            raise TranscriptionError('Groq returned an unexpected transcript format.')
        return text.strip()
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise TranscriptionError('Groq rate limit or quota reached. Listening stopped. Check your Groq limits before restarting; no paid transcription fallback is enabled.') from None
        if error.code in (401,403):
            raise TranscriptionError('Groq authentication failed. Check GROQ_API_KEY and model access, then restart.') from None
        raise TranscriptionError(f'Groq transcription failed (HTTP {error.code}). Listening stopped; check model access and service status.') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TranscriptionError('Groq transcription connection failed or timed out. Listening stopped; check your connection and restart.') from None
    except (ValueError, TypeError):
        raise TranscriptionError('Groq returned an unreadable transcription response.') from None
