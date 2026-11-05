import io
import json
import ssl
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import managed_ai
from account_store import AccountStore


class ManagedConnectionTests(unittest.TestCase):
    def setUp(self):
        managed_ai.disconnect()
        self.addCleanup(setattr, managed_ai, 'account_store', None)
        managed_ai._config = {'gatewayUrl': 'https://synthetic.example/api/ai', 'firebaseApiKey': 'synthetic'}
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


    @unittest.skipUnless(sys.platform == 'win32', 'Windows DPAPI required')
    def test_saved_sign_in_restores_and_explicit_sign_out_removes_it(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'account-session.dpapi'
            managed_ai.account_store = AccountStore(path)
            usage = {'aiEnabled': True, 'trialUpdatedAtMs': 100, 'remainingTrialMs': 55000}
            with patch.object(managed_ai, 'post', return_value=usage):
                managed_ai.connect('initial-id', 'initial-refresh')
            self.assertNotIn(b'initial-refresh', path.read_bytes())

            # Simulate app exit and launch with fresh in-memory state.
            managed_ai.disconnect()
            managed_ai.account_store = AccountStore(path)
            self.assertFalse(managed_ai.connected())
            with patch.object(managed_ai, 'post', side_effect=TimeoutError()):
                with self.assertRaises(TimeoutError):
                    managed_ai.prepare_restore()
            self.assertEqual(managed_ai.account_store.load(), 'initial-refresh')

            renewed = {'id_token': 'restored-id', 'refresh_token': 'rotated-refresh', 'expires_in': '3600'}
            with patch.object(managed_ai, 'post', side_effect=[renewed, usage]) as post:
                managed_ai.finish_restore(*managed_ai.prepare_restore())
            self.assertIn(b'refresh_token=initial-refresh', post.call_args_list[0].args[1])
            self.assertEqual(post.call_args_list[1].args[2]['Authorization'], 'Bearer restored-id')
            self.assertTrue(managed_ai.connected())
            self.assertEqual(managed_ai.remaining_trial_ms(), 55000)
            self.assertEqual(AccountStore(path).load(), 'rotated-refresh')

            managed_ai.sign_out()
            self.assertFalse(managed_ai.connected())
            self.assertFalse(path.exists())

    def test_transient_token_refresh_error_does_not_sign_out(self):
        managed_ai._session.update(id='test', refresh='test', expires=0, generation='test')
        with patch.object(managed_ai, 'post', side_effect=TimeoutError()):
            with self.assertRaisesRegex(managed_ai.ManagedError, 'Could not refresh'):
                managed_ai.call({'kind': 'usage'})
        self.assertTrue(managed_ai.connected())


if __name__ == '__main__':
    unittest.main()
