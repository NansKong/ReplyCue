"""Firebase session and fixed-origin managed AI transport."""
import base64
import io
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import uuid


class ManagedError(ValueError):
    pass


class InvalidRefreshToken(ManagedError):
    pass


account_store = None
_config = {}
_session = {}
_lock = threading.RLock()
remaining = None
trial_limit = None
minimum_turn = None
ai_available = None
unlimited = False
trial_limit_ms = None
_trial_remaining_ms = None
_trial_received_at = 0
_trial_updated_at = 0
_trial_running = False
_session_id = None
_trial_issue = None
_heartbeat_stop = threading.Event()
_lease_lock = threading.Lock()
_pause_done = threading.Event()
_pause_done.set()


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
    global remaining, trial_limit, minimum_turn, ai_available, unlimited
    global trial_limit_ms, _trial_remaining_ms, _trial_running, _session_id, _trial_issue, _trial_updated_at
    with _lock:
        _heartbeat_stop.set()
        _session_id = None
        _trial_running = False
        _trial_remaining_ms = trial_limit_ms = _trial_issue = None
        _trial_updated_at = 0
        unlimited = False
        _session.clear()
        remaining = trial_limit = minimum_turn = ai_available = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(url, body, headers, on_update=None, interrupted=lambda: False, timeout_seconds=19):
    request = urllib.request.Request(url, data=body, headers=headers)
    deadline = time.monotonic() + timeout_seconds
    for attempt in range(3):
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                    request, timeout=max(0.1, deadline - time.monotonic())) as response:
                if on_update and response.headers.get_content_type() == 'application/x-ndjson':
                    return read_answer_stream(response, on_update, interrupted, deadline)
                return json.loads(response.read(1024 * 1024))
        except (urllib.error.URLError, ssl.SSLCertVerificationError) as error:
            reason = error.reason if isinstance(error, urllib.error.URLError) else error
            if not isinstance(reason, ssl.SSLCertVerificationError):
                raise
            # TLS failed before HTTP headers or the body were sent. Only a new,
            # fully verified handshake is retried, so a paid request is not replayed.
            if attempt == 2 or deadline - time.monotonic() < 0.5:
                raise ManagedError(
                    'Secure connection verification failed. Check your computer clock '
                    'and any VPN, proxy, or antivirus HTTPS inspection, then try again.'
                ) from None
            time.sleep(0.15 * (attempt + 1))


def read_answer_stream(response, on_update, interrupted, deadline):
    for line in response:
        if interrupted():
            raise ManagedError('Answer request canceled.')
        if time.monotonic() > deadline:
            raise TimeoutError('Answer stream deadline exceeded')
        if len(line) > 262144:
            raise ManagedError('The answer stream returned an oversized update.')
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ManagedError('The answer stream returned an invalid update.')
        if event.get('error'):
            raise ManagedError('The answer stream was interrupted. Resume to try again.')
        text = event.get('text')
        if not isinstance(text, str) or len(text) > 100000:
            raise ManagedError('The answer stream returned invalid text.')
        if event.get('done') is True:
            return event
        on_update(text)
    raise ManagedError('The answer stream ended before completion. Resume to try again.')


def valid_token(token):
    return isinstance(token, str) and 0 < len(token) < 8192 and not any(c.isspace() for c in token)


def refresh_credentials(refresh_token):
    if not valid_token(refresh_token):
        raise InvalidRefreshToken('Sign in again to continue.')
    key = urllib.parse.quote(_config['firebaseApiKey'], safe='')
    try:
        result = post('https://securetoken.googleapis.com/v1/token?key='+key,
                      urllib.parse.urlencode({'grant_type': 'refresh_token',
                                              'refresh_token': refresh_token}).encode(),
                      {'Content-Type': 'application/x-www-form-urlencoded'})
    except urllib.error.HTTPError as error:
        if error.code in (400, 401, 403):
            try:
                code = json.loads(error.read(4096))['error']['message']
            except (OSError, ValueError, KeyError, TypeError):
                code = None
            if code in ('TOKEN_EXPIRED', 'USER_DISABLED', 'USER_NOT_FOUND', 'INVALID_REFRESH_TOKEN'):
                raise InvalidRefreshToken('Your saved session expired. Sign in again to continue.') from None
        raise
    id_token, refresh_token = result['id_token'], result['refresh_token']
    if not all(map(valid_token, (id_token, refresh_token))):
        raise ManagedError('Firebase returned an invalid account session.')
    return {'id': id_token, 'refresh': refresh_token,
            'expires': time.monotonic()+max(0, int(result['expires_in'])-60)}


def remember(refresh_token):
    if account_store:
        try:
            account_store.save(refresh_token)
        except OSError:
            raise ManagedError('Windows could not save your ReplyCue sign-in. Try again.') from None


def sign_out():
    with _lock:
        if account_store:
            try:
                account_store.clear()
            except OSError:
                raise ManagedError('Windows could not remove the saved sign-in. Try again.') from None
        disconnect()


def connect(id_token, refresh_token):
    if not enabled() or not all(map(valid_token, (id_token, refresh_token))):
        raise ManagedError('Invalid account session.')
    if not _pause_done.wait(22):
        raise ManagedError('Finishing the previous session. Try again shortly.')
    with _lock:
        _session.update(id=id_token, refresh=refresh_token, expires=time.monotonic()+3000, generation=uuid.uuid4().hex)
        try:
            result = call({'kind': 'usage'})
            remember(refresh_token)
            update_trial_settings(result)
        except Exception:
            disconnect()
            raise


def prepare_restore():
    """Validate a saved session off the GUI thread before installing it."""
    refresh_token = account_store.load()
    credentials = refresh_credentials(refresh_token)
    if credentials['refresh'] != refresh_token:
        remember(credentials['refresh'])
    usage = post(_config['gatewayUrl'], b'{"kind":"usage","trialProtocol":1}',
                 {'Content-Type': 'application/json', 'Authorization': 'Bearer '+credentials['id']})
    if not isinstance(usage, dict):
        raise ManagedError('The account service returned an invalid response.')
    return credentials, usage


def finish_restore(credentials, usage):
    with _lock:
        _session.update(**credentials, generation=uuid.uuid4().hex)
        update_balance(usage)
        update_trial_settings(usage)


def update_trial_settings(result):
    global trial_limit, minimum_turn, ai_available
    trial_limit = result.get('limitMicroUsd')
    minimum_turn = result.get('minimumTurnMicroUsd')
    ai_available = result.get('aiEnabled')
    update_time(result)


def update_time(result):
    global unlimited, trial_limit_ms, _trial_remaining_ms
    global _trial_updated_at, _trial_received_at, _trial_running
    timestamp = result.get('trialUpdatedAtMs')
    if type(timestamp) is not int:
        return
    with _lock:
        if timestamp < _trial_updated_at:
            return
        unlimited = result.get('unlimited') is True
        trial_limit_ms = result.get('trialLimitMs')
        _trial_remaining_ms = result.get('remainingTrialMs')
        _trial_running = result.get('trialRunning') is True
        _trial_updated_at = timestamp
        _trial_received_at = time.monotonic()


def remaining_trial_ms():
    with _lock:
        if type(_trial_remaining_ms) is not int:
            return None
        elapsed = (time.monotonic() - _trial_received_at) * 1000 if _trial_running and _session_id else 0
        return max(0, int(_trial_remaining_ms - elapsed))


def session_issue():
    global _trial_issue
    with _lock:
        issue, _trial_issue = _trial_issue, None
        return issue


def begin_session():
    global _session_id, _heartbeat_stop, _trial_issue
    if not enabled() or unlimited:
        return
    if not _pause_done.wait(22):
        raise ManagedError('Finishing the previous session. Try again shortly.')
    with _lease_lock:
        ident = str(uuid.uuid4())
        _trial_issue = None
        _session_id = ident
        try:
            call({'kind': 'session-start', 'sessionId': ident})
        except Exception:
            _session_id = None
            raise
        _heartbeat_stop = threading.Event()
        threading.Thread(target=_heartbeat, args=(ident, _heartbeat_stop), daemon=True).start()


def _heartbeat(ident, stop):
    global _trial_issue
    while not stop.wait(10):
        try:
            with _lease_lock:
                if stop.is_set():
                    return
                call({'kind': 'session-heartbeat', 'sessionId': ident})
        except ManagedError as error:
            if not stop.is_set():
                _trial_issue = str(error)
            return


def end_session():
    global _session_id, _trial_remaining_ms, _trial_running
    with _lock:
        ident = _session_id
        if not ident:
            return
        _trial_remaining_ms = remaining_trial_ms()
        _session_id = None
        _trial_running = False
        _heartbeat_stop.set()
        _pause_done.clear()
    def finish():
        try:
            with _lease_lock:
                call({'kind': 'session-stop', 'sessionId': ident})
        except ManagedError:
            # The server lease ends within 30 seconds if the network is lost.
            pass
        finally:
            _pause_done.set()
    threading.Thread(target=finish, daemon=True).start()


def update_balance(result):
    global remaining
    value = result.get('remainingMicroUsd')
    if type(value) is int and value >= 0:
        with _lock:
            # Transcription and answers may finish in a different order than
            # their reservations. An older response must not raise the balance.
            remaining = value if remaining is None else min(remaining, value)



def call(payload, on_update=None, interrupted=lambda: False):
    with _lock:
        if not _session:
            raise ManagedError('Sign in to ReplyCue first.')
        try:
            if time.monotonic() >= _session['expires']:
                previous_refresh = _session['refresh']
                credentials = refresh_credentials(previous_refresh)
                if credentials['refresh'] != previous_refresh:
                    remember(credentials['refresh'])
                _session.update(credentials)
            token = _session['id']
            generation = _session.get('generation')
            payload = {'trialProtocol': 1, **payload}
            if _session_id and 'sessionId' not in payload:
                payload['sessionId'] = _session_id
        except InvalidRefreshToken:
            sign_out()
            raise
        except ManagedError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise ManagedError('Could not refresh your sign-in. Check your connection and try again.') from None
    try:
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+token}
        def publish(text):
            with _lock:
                if generation != _session.get('generation'):
                    raise ManagedError('The previous account session ended.')
            on_update(text)
        if on_update:
            result = post(_config['gatewayUrl'], json.dumps({**payload, 'stream': True}).encode(),
                          headers, publish, interrupted, timeout_seconds=32 if payload.get('kind') in ('mock-assessment', 'mock-inspect', 'mock-solution') else 19)
        else:
            result = post(_config['gatewayUrl'], json.dumps(payload).encode(), headers)
        with _lock:
            if generation != _session.get('generation'):
                raise ManagedError('The previous account session ended.')
            update_balance(result)
            update_time(result)
        return result
    except urllib.error.HTTPError as error:
        with _lock:
            if generation != _session.get('generation'):
                raise ManagedError('The previous account session ended.') from None
            if error.code == 401:
                disconnect()
        try:
            details = json.loads(error.read(4096))
            if not isinstance(details, dict):
                details = {}
        except (OSError, ValueError):
            details = {}
        update_balance(details)
        if error.code in (409, 426, 429):
            message = {
                'trial': 'Your one-hour trial has ended. View plan options in your ReplyCue profile.',
                'session': 'Your session check-in expired. Resume to continue.',
                'session_in_use': 'This account has an active session on another device. End it first.',
                'upgrade': 'Install the latest ReplyCue update to use your one-hour trial.',
                'provider_rate': 'The AI provider is busy. Try again shortly.',
                'rate': 'Too many requests. Try again shortly.',
                'global': 'The beta is temporarily at capacity.',
            }.get(details.get('code'))
            if message:
                raise ManagedError(message) from None
        message = {401: 'Sign in again to continue.', 403: 'Verify your email before starting.',
                   429: 'The trial limit or request rate limit was reached.'}.get(error.code)
        raise ManagedError(message or 'Managed AI could not complete this request.') from None
    except ManagedError:
        raise
    except (TimeoutError, urllib.error.URLError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, TimeoutError):
            raise ManagedError('The AI connection timed out. Check your connection and try again.') from None
        raise ManagedError('The AI service could not be reached. Check your internet connection and try again.') from None
    except OSError:
        raise ManagedError('The AI connection was interrupted. Try again when your connection is stable.') from None
    except ValueError:
        raise ManagedError('The AI service returned an unreadable response. Try again shortly.') from None


def transcribe(audio):
    with wave.open(io.BytesIO(audio), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ManagedError('Unsupported audio format.')
        pcm = source.readframes(source.getnframes())
    return call({'kind': 'transcribe', 'pcm': base64.b64encode(pcm).decode('ascii')})['text'].strip()
