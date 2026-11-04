import io
import json
import ssl
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import managed_ai


class ManagedConnectionTests(unittest.TestCase):
    def setUp(self):
        managed_ai.disconnect()
        managed_ai._config = {'gatewayUrl': 'https://synthetic.example/api/ai'}
        self.certificate_error = urllib.error.URLError(
            ssl.SSLCertVerificationError(1, 'synthetic untrusted certificate'))

    def tearDown(self):
        managed_ai.disconnect()
        managed_ai._config = {}

    def test_certificate_failure_retries_before_sending_the_request(self):
        response = io.BytesIO(json.dumps({'text': 'Synthetic answer.'}).encode())
        with patch('managed_ai.urllib.request.build_opener') as builder, patch('managed_ai.time.sleep'):
            builder.return_value.open.side_effect = [self.certificate_error, response]
            result = managed_ai.post('https://synthetic.example/api/ai', b'{}', {})
            self.assertEqual(result['text'], 'Synthetic answer.')
            self.assertEqual(builder.return_value.open.call_count, 2)
            self.assertIsInstance(builder.call_args.args[0], managed_ai.NoRedirect)

    def test_persistent_certificate_failure_remains_verified_and_bounded(self):
        with patch('managed_ai.urllib.request.build_opener') as builder, patch('managed_ai.time.sleep'):
            builder.return_value.open.side_effect = self.certificate_error
            with self.assertRaisesRegex(managed_ai.ManagedError, 'Secure connection verification failed'):
                managed_ai.post('https://synthetic.example/api/ai', b'{}', {})
            self.assertEqual(builder.return_value.open.call_count, 3)

    def test_http_failure_is_not_retried(self):
        failure = urllib.error.HTTPError('https://synthetic.example', 502, 'upstream failure', {}, io.BytesIO(b'{}'))
        with patch('managed_ai.urllib.request.build_opener') as builder:
            builder.return_value.open.side_effect = failure
            with self.assertRaises(urllib.error.HTTPError):
                managed_ai.post('https://synthetic.example/api/ai', b'{}', {})
            self.assertEqual(builder.return_value.open.call_count, 1)

    def test_timeout_is_not_retried(self):
        with patch('managed_ai.urllib.request.build_opener') as builder:
            builder.return_value.open.side_effect = urllib.error.URLError(TimeoutError())
            with self.assertRaises(urllib.error.URLError):
                managed_ai.post('https://synthetic.example/api/ai', b'{}', {})
            self.assertEqual(builder.return_value.open.call_count, 1)

    def test_specific_connection_error_reaches_the_app(self):
        managed_ai._session.update(id='synthetic-id', refresh='synthetic-refresh', expires=float('inf'), generation='test')
        with patch.object(managed_ai, 'post', side_effect=managed_ai.ManagedError('Secure connection verification failed.')):
            with self.assertRaisesRegex(managed_ai.ManagedError, '^Secure connection verification failed'):
                managed_ai.call({'kind': 'answer', 'prompt': 'Synthetic prompt'})


if __name__ == '__main__':
    unittest.main()
