"""Memory-only Firebase session and fixed-origin managed AI transport."""
import base64
import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave


class ManagedError(ValueError):
    pass


_config = {}
_session = {}
_lock = threading.RLock()
remaining = None
trial_limit = None
minimum_turn = None
ai_available = None


def load(path):
    global _config
    if path.exists():
        _config = json.loads(path.read_text(encoding='utf-8-sig'))
        if enabled():
            url = urllib.parse.urlsplit(_config['gatewayUrl'])
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment or url.query:
                raise ValueError('Invalid managed gateway URL')


def enabled():
    return bool(_config.get('gatewayUrl'))


def connected():
    return bool(_session)


def disconnect():
    global remaining, trial_limit, minimum_turn, ai_available
    with _lock:
        _session.clear()
        remaining = trial_limit = minimum_turn = ai_available = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(url, body, headers):
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=19) as response:
        return json.loads(response.read(1024 * 1024))


def connect(id_token, refresh_token):
    if not enabled() or not all(isinstance(value, str) and 0 < len(value) < 8192
                               and not any(c.isspace() for c in value)
                               for value in (id_token, refresh_token)):
        raise ManagedError('Invalid account session.')
    with _lock:
        _session.update(id=id_token, refresh=refresh_token, expires=time.monotonic()+3000)
        try:
            result = call({'kind': 'usage'})
            update_trial_settings(result)
        except Exception:
            disconnect()
            raise


def update_trial_settings(result):
    global trial_limit, minimum_turn, ai_available
    trial_limit = result.get('limitMicroUsd')
    minimum_turn = result.get('minimumTurnMicroUsd')
    ai_available = result.get('aiEnabled')


def update_balance(result):
    global remaining
    value = result.get('remainingMicroUsd')
    if type(value) is int and value >= 0:
        with _lock:
            # Transcription and answers may finish in a different order than
            # their reservations. An older response must not raise the balance.
            remaining = value if remaining is None else min(remaining, value)



def call(payload):
    with _lock:
        if not _session:
            raise ManagedError('Sign in to ReplyCue first.')
        try:
            if time.monotonic() >= _session['expires']:
                key = urllib.parse.quote(_config['firebaseApiKey'], safe='')
                result = post('https://securetoken.googleapis.com/v1/token?key='+key,
                              urllib.parse.urlencode({'grant_type': 'refresh_token',
                                                     'refresh_token': _session['refresh']}).encode(),
                              {'Content-Type': 'application/x-www-form-urlencoded'})
                _session.update(id=result['id_token'], refresh=result['refresh_token'],
                                expires=time.monotonic()+max(0, int(result['expires_in'])-60))
            token = _session['id']
        except (OSError, ValueError, KeyError):
            disconnect()
            raise ManagedError('Sign in again to continue.') from None
    try:
        result = post(_config['gatewayUrl'], json.dumps(payload).encode(),
                      {'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
        update_balance(result)
        return result
    except urllib.error.HTTPError as error:
        if error.code == 401:
            disconnect()
        try:
            details = json.loads(error.read(4096))
            if not isinstance(details, dict):
                details = {}
        except (OSError, ValueError):
            details = {}
        update_balance(details)
        if error.code == 429:
            message = {
                'trial': 'Your trial allowance is used up. View plan options in your ReplyCue profile.',
                'provider_rate': 'The AI provider is busy. Try again shortly.',
                'rate': 'Too many requests. Try again shortly.',
                'global': 'The beta is temporarily at capacity.',
            }.get(details.get('code'))
            if message:
                raise ManagedError(message) from None
        message = {401: 'Sign in again to continue.', 403: 'Verify your email before starting.',
                   429: 'The trial limit or request rate limit was reached.'}.get(error.code)
        raise ManagedError(message or 'Managed AI could not complete this request.') from None
    except (OSError, ValueError):
        raise ManagedError('Could not connect to managed AI.') from None


def transcribe(audio):
    with wave.open(io.BytesIO(audio), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ManagedError('Unsupported audio format.')
        pcm = source.readframes(source.getnframes())
    return call({'kind': 'transcribe', 'pcm': base64.b64encode(pcm).decode('ascii')})['text'].strip()
