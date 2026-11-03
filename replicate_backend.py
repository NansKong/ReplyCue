"""Replicate predictions with bounded polling and best-effort cancellation."""
import base64
import json
import time
import urllib.request
import urllib.parse
import urllib.error

class ReplicateBackend:
    _versions = {}
    def __init__(self, token, interrupted):
        self.token = token
        self.interrupted = interrupted

    def request(self, path, body=None):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Invalid API path')
        req = urllib.request.Request('https://api.replicate.com/v1'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer '+self.token, 'User-Agent':'InterviewCopilot/0.1', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)

    def predict(self, model, inputs, update=None):
        parts = model.split(':', 1)
        owner_name = parts[0]
        if len(owner_name.split('/')) != 2 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./' for c in owner_name):
            raise ValueError('Expected owner/model identifier')
        cached = self._versions.get(model)
        if cached and cached[0] > time.monotonic():
            version = cached[1]
        elif len(parts) == 2:
            version = self.request('/models/'+owner_name+'/versions/'+parts[1])
        else:
            version = self.request('/models/'+owner_name)['latest_version']
        if not version:
            raise ValueError('Model has no accessible version')
        self._versions[model] = (time.monotonic()+300, version)
        schema = version.get('openapi_schema', {}).get('components', {}).get('schemas', {}).get('Input', {})
        properties = schema.get('properties', {})
        # Only send optional controls if the current model schema supports them.
        filtered = {key:value for key,value in inputs.items() if key in properties}
        if 'prompt' in inputs and 'prompt' not in filtered:
            raise ValueError('Answer model must accept a prompt input')
        if 'audio' in inputs:
            audio_key = next((k for k in ('audio','audio_file') if k in properties), None)
            if not audio_key:
                raise ValueError('Transcription model must accept audio or audio_file')
            filtered[audio_key] = inputs['audio']
        missing = set(schema.get('required', []))-set(filtered)
        missing = {k for k in missing if 'default' not in properties.get(k,{})}
        if missing:
            raise ValueError('Model requires unsupported inputs')
        if self.interrupted():
            return None
        prediction = self.request('/predictions', {'version': version['id'], 'input': filtered, 'stream': False})
        prediction_id = prediction['id']
        deadline = time.monotonic()+90
        last_output = None
        try:
            # Poll authoritative snapshots. A short-lived SSE connection must not
            # interfere with final completion on this provider integration.
            while True:
                if self.interrupted():
                    self.request('/predictions/'+prediction_id+'/cancel', {})
                    return None
                if update and prediction.get('output') is not None and prediction['output'] != last_output:
                    last_output = prediction['output']
                    update(last_output)
                if prediction['status'] == 'succeeded':
                    return prediction['output']
                if prediction['status'] in ('failed','canceled'):
                    raise RuntimeError('Prediction failed')
                if time.monotonic() >= deadline:
                    raise TimeoutError('Prediction deadline exceeded')
                time.sleep(0.35)
                prediction = self.request('/predictions/'+prediction_id)
        except Exception:
            try:
                self.request('/predictions/'+prediction_id+'/cancel', {})
            except Exception:
                pass
            raise

    def consume_stream(self, url, update, deadline):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not (parsed.hostname in ('stream.replicate.com', 'streaming.api.replicate.com') or (parsed.hostname or '').endswith('.c.replicate.net')):
            raise ValueError('Unexpected streaming host')
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer '+self.token,
            'User-Agent': 'InterviewCopilot/0.1', 'Accept': 'text/event-stream'})
        text, event, data = '', '', []
        with urllib.request.urlopen(request, timeout=1.5) as response:
            for raw in response:
                if self.interrupted():
                    return
                if time.monotonic() > deadline:
                    raise TimeoutError('Stream deadline exceeded')
                line = raw.decode('utf-8').rstrip('\r\n')
                if not line:
                    payload = '\n'.join(data)
                    if event == 'output':
                        text += payload
                        update(text)
                    elif event == 'error':
                        raise RuntimeError('Prediction stream reported an error')
                    elif event == 'done':
                        return
                    event, data = '', []
                elif line.startswith('event:'):
                    event = line[6:].strip()
                elif line.startswith('data:'):
                    value = line[5:]
                    data.append(value[1:] if value.startswith(' ') else value)


def audio_input(data):
    return 'data:audio/wav;base64,'+base64.b64encode(data).decode('ascii')

def output_text(output):
    if isinstance(output,str):
        return output
    if isinstance(output,list):
        return ''.join(output_text(item) for item in output)
    if isinstance(output,dict):
        return str(output.get('text', output.get('transcription','')))
    return ''
