"""Transport integration checks: no microphone, audio capture, or provider requests."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
class BridgeTests(unittest.TestCase):
    def exercise(self, executable):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / '.env'
            document = Path(folder) / 'resume.txt'
            document.write_text('Synthetic example: Python and SQL.', encoding='utf-8')
            commands = [
                {'id': 1, 'action': 'state'},
                {'id': 2, 'action': 'configure', 'data': {'GROQ_API_KEY': 'synthetic-groq-secret', 'REPLICATE_API_TOKEN': 'synthetic-replicate-secret'}},
                {'id': 3, 'action': 'import', 'data': {'path': str(document)}},
                {'id': 4, 'action': 'start', 'data': {'resume': 'Synthetic résumé', 'jd': 'Synthetic role', 'consent': False}},
                {'id': 7, 'action': 'overlay-expand'},
                {'id': 8, 'action': 'overlay-collapse'},
                {'id': 6, 'action': 'sources'},
                {'id': 5, 'action': 'quit'}]
            completed = subprocess.run([*executable, '--config', str(config)], input='\n'.join(json.dumps(c) for c in commands)+'\n', capture_output=True, text=True, timeout=25)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn('synthetic-groq-secret', completed.stdout)
            self.assertNotIn('synthetic-replicate-secret', completed.stdout)
            responses = {item['id']: item for line in completed.stdout.splitlines() if (item := json.loads(line)).get('id')}
            self.assertFalse(responses[1]['result']['configured'])
            self.assertTrue(responses[2]['result']['configured'])
            self.assertIn('Python and SQL', responses[3]['result'])
            self.assertFalse(responses[4]['result']['live'])
            self.assertIn('cloud-processing', responses[4]['result']['status'])
            self.assertIsInstance(responses[6]['result']['audioSources'], list)
            self.assertIsNone(responses[7]['result'])
            self.assertIsNone(responses[8]['result'])
            self.assertFalse(responses[6]['result']['overlayVisible'])
            self.assertEqual(len(responses), 8)
    def test_source_bridge(self):
        self.exercise([str(ROOT / '.venv/Scripts/python.exe'), str(Path(__file__).with_name('bridge.py'))])
    def test_packaged_bridge(self):
        self.exercise([str(Path(__file__).parent / 'dist/CopilotEngine/CopilotEngine.exe')])

    def test_packaged_audio_buffer(self):
        result = subprocess.run([str(Path(__file__).parent / 'dist/CopilotEngine/CopilotEngine.exe'),
                                 '--config', str(Path(__file__).parent / 'unused-self-test.env'),
                                 '--audio-self-test'], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['audio_buffer_check'], 'passed')
        self.assertEqual(json.loads(result.stdout)['noise_filter_check'], 'passed')

if __name__ == '__main__': unittest.main()
