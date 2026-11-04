import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import managed_ai


class TrialTimeTests(unittest.TestCase):
    def setUp(self):
        managed_ai.disconnect()
        managed_ai._config = {'gatewayUrl': 'https://synthetic.example/api/ai'}
        self.requests = []
        self.used = 0
        self.stamp = 1

    def tearDown(self):
        managed_ai.end_session()
        managed_ai._pause_done.wait(2)
        managed_ai.disconnect()
        managed_ai._config = {}

    def respond(self, url, body, headers):
        payload = json.loads(body)
        self.requests.append(payload)
        self.stamp += 1
        return {
            'aiEnabled': True, 'unlimited': False, 'trialLimitMs': 3600000,
            'remainingTrialMs': 3600000 - self.used,
            'trialRunning': payload['kind'] in ('session-start', 'session-heartbeat'),
            'trialUpdatedAtMs': self.stamp,
        }

    def test_pause_and_resume_preserve_remaining_time(self):
        with patch.object(managed_ai, 'post', side_effect=self.respond):
            managed_ai.connect('synthetic-id', 'synthetic-refresh')
            managed_ai.begin_session()
            first_id = self.requests[-1]['sessionId']
            self.assertEqual(self.requests[-1]['trialProtocol'], 1)
            self.assertLessEqual(managed_ai.remaining_trial_ms(), 3600000)
            self.used = 5000
            managed_ai.end_session()
            self.assertTrue(managed_ai._pause_done.wait(2))
            frozen = managed_ai.remaining_trial_ms()
            time.sleep(0.02)
            self.assertEqual(managed_ai.remaining_trial_ms(), frozen)
            managed_ai.begin_session()
            self.assertNotEqual(self.requests[-1]['sessionId'], first_id)
            self.assertLessEqual(managed_ai.remaining_trial_ms(), 3595000)
            managed_ai.end_session()
            self.assertTrue(managed_ai._pause_done.wait(2))

    def test_unlimited_accounts_do_not_start_a_trial_timer(self):
        with patch.object(managed_ai, 'post', return_value={
            'unlimited': True, 'trialUpdatedAtMs': 10, 'remainingTrialMs': None,
            'trialLimitMs': None, 'aiEnabled': True,
        }) as post:
            managed_ai.connect('synthetic-id', 'synthetic-refresh')
            managed_ai.begin_session()
            self.assertIsNone(managed_ai.remaining_trial_ms())
            self.assertEqual(post.call_count, 1)
            managed_ai.end_session()

    def test_old_responses_cannot_restart_a_paused_timer(self):
        managed_ai.update_time({'trialUpdatedAtMs': 20, 'remainingTrialMs': 3500000,
                                'trialLimitMs': 3600000, 'trialRunning': False})
        managed_ai.update_time({'trialUpdatedAtMs': 10, 'remainingTrialMs': 3600000,
                                'trialRunning': True})
        self.assertEqual(managed_ai.remaining_trial_ms(), 3500000)
        self.assertFalse(managed_ai._trial_running)


if __name__ == '__main__':
    unittest.main()
