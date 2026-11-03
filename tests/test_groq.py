import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from groq_backend import transcribe,TranscriptionError
from cloud import CloudJob

class TranscriptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QCoreApplication.instance() or QCoreApplication([])

    def test_multipart_and_text(self):
        response=io.BytesIO(json.dumps({'text':'  What is Python?  '}).encode())
        with patch('groq_backend.urllib.request.urlopen',return_value=response) as send:
            self.assertEqual(transcribe(b'RIFF-audio','test-key'),'What is Python?')
        request=send.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.groq.com/openai/v1/audio/transcriptions')
        self.assertIn(b'whisper-large-v3-turbo',request.data)
        self.assertIn(b'filename="turn.wav"',request.data)
        self.assertIn(b'RIFF-audio',request.data)

    def test_stop_before_upload(self):
        with patch('groq_backend.urllib.request.urlopen') as send:
            self.assertEqual(transcribe(b'audio','test',interrupted=lambda:True),'')
            send.assert_not_called()

    def test_rate_limit_does_not_generate_answer(self):
        error=urllib.error.HTTPError('https://api.groq.com',429,'quota',{},None)
        job=CloudJob('replicate-test','google/gemini-2.5-flash','whisper-large-v3-turbo',{},audio=b'audio',groq_key='groq-test')
        problems=[]
        job.problem.connect(problems.append)
        with patch('groq_backend.urllib.request.urlopen',side_effect=error), patch('replicate_backend.ReplicateBackend.predict') as predict:
            job.run()
            predict.assert_not_called()
        self.assertIn('quota',problems[0])
        self.assertNotIn('groq-test',problems[0])

    def test_success_routes_audio_only_to_groq(self):
        job=CloudJob('replicate-test','google/gemini-2.5-flash','whisper-large-v3-turbo',{'Resume':'Python developer'},audio=b'audio',groq_key='groq-test')
        heard=[]; answers=[]
        job.transcript.connect(heard.append); job.answer.connect(answers.append)
        with patch('groq_backend.transcribe',return_value='Describe your Python experience') as stt, patch('replicate_backend.ReplicateBackend.predict',return_value=['I develop Python services.']) as predict:
            job.run()
        self.assertEqual(stt.call_args.args[1],'groq-test')
        self.assertEqual(predict.call_count,1)
        self.assertEqual(predict.call_args.args[0],'google/gemini-2.5-flash')
        self.assertNotIn('audio',predict.call_args.args[1])
        self.assertTrue(heard and answers)

if __name__=='__main__': unittest.main()
