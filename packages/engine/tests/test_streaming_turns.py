import io
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import managed_ai
from app import QApplication, Studio
from cloud import CloudJob
from turn_detection import required_silence

APP = QApplication.instance() or QApplication([])


class StreamingTurnTests(unittest.TestCase):
    def studio(self):
        studio = Studio()
        studio.live = True
        self.addCleanup(studio.close)
        self.addCleanup(studio.stop_live)
        return studio

    def test_adaptive_turn_detection_waits_for_continuations(self):
        self.assertEqual(required_silence('What is computer vision?'), .7)
        for fragment in ['Can you walk me through', 'How do you choose between', 'Explain caching and',
                         'What is caching,', 'Can you explain why...']:
            self.assertEqual(required_silence(fragment), 1.7)
        self.assertEqual(required_silence('Explain the caching tradeoffs.'), 1.05)

    def test_early_pause_does_not_finalize_the_question(self):
        studio = self.studio()
        studio.fragments = ['Can you walk me through']
        with patch('app.time.monotonic', return_value=10):
            studio.last_speech_at = 9.3
            studio.finish_turn()
        self.assertTrue(studio.turn_timer.isActive())
        self.assertEqual(studio.pending_questions, [])
        self.assertEqual(studio.fragments, ['Can you walk me through'])

    def test_preview_waits_for_a_sentence_then_appends_without_resetting_read_delay(self):
        studio = self.studio()
        worker = CloudJob('', '', '', {}, question='What is Python?')
        worker.record_index = 0
        worker.coding_answer = False
        studio.job = worker
        studio.qa_records = [{'question': worker.question, 'answer': '', 'status': 'Generating'}]
        worker.answer.connect(studio.show_answer)
        worker.finished.connect(studio.answer_finished)
        worker.answer.emit('Python is')
        self.assertEqual(studio.panel.live_text, '')
        worker.answer.emit('Python is a programming language.')
        self.assertEqual(studio.panel.live_text, 'Python is a programming language.')
        delay = studio.panel.read_after
        worker.answer.emit('Python is a programming language. I use it for APIs.')
        self.assertEqual(studio.panel.read_after, delay)
        worker.final_answer = 'Python is a programming language. I use it for APIs.'
        worker.finished.emit()
        self.assertEqual(studio.reader_queue, [])
        self.assertEqual(len(studio.session_memory), 1)
        self.assertEqual(studio.qa_records[0]['status'], 'Complete')

    def test_progress_does_not_replace_an_answer_while_it_is_being_read(self):
        studio = self.studio()
        studio.panel.reveal('Previous answer stays visible.')
        studio.reader_hold.start(20000)
        worker = CloudJob('', '', '', {}, question='A follow-up?')
        studio.preview_answer(worker, 'The new answer is ready.')
        self.assertEqual(studio.panel.live_text, 'Previous answer stays visible.')

    def test_stream_requires_explicit_completion_and_preserves_unicode(self):
        updates = []
        messages = [{'text': 'Résumé ', 'done': False},
                    {'text': 'Résumé evidence.', 'done': False},
                    {'text': 'Résumé evidence.', 'done': True}]
        response = io.BytesIO(('\n'.join(json.dumps(m) for m in messages)+'\n').encode())
        result = managed_ai.read_answer_stream(response, updates.append, lambda: False, time.monotonic()+2)
        self.assertEqual(updates, ['Résumé ', 'Résumé evidence.'])
        self.assertTrue(result['done'])
        with self.assertRaisesRegex(managed_ai.ManagedError, 'before completion'):
            managed_ai.read_answer_stream(io.BytesIO(b'{"text":"Partial","done":false}\n'),
                                          lambda _: None, lambda: False, time.monotonic()+2)

    def test_no_stream_updates_after_cancellation(self):
        with self.assertRaisesRegex(managed_ai.ManagedError, 'canceled'):
            managed_ai.read_answer_stream(io.BytesIO(b'{"text":"Answer.","done":false}\n'),
                                          lambda _: self.fail('Published after cancellation'),
                                          lambda: True, time.monotonic()+2)


if __name__ == '__main__':
    unittest.main()
