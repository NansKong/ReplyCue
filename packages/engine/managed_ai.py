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
    global remaining
    with _lock:
        _session.clear()
        remaining = None


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
            call({'kind': 'usage'})
        except Exception:
            disconnect()
            raise


def call(payload):
    global remaining
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
        if 'remainingMicroUsd' in result:
            remaining = result['remainingMicroUsd']
        return result
    except urllib.error.HTTPError as error:
        if error.code == 401:
            disconnect()
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
