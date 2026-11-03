import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replicate_backend import ReplicateBackend
from app import QApplication,Studio
from PySide6.QtTest import QTest
APP=QApplication.instance() or QApplication([])
class AnswerRegressionTests(unittest.TestCase):
 def test_gemini_model_name_with_period(self):
  backend=ReplicateBackend('test',lambda:False)
  version={'id':'test-version','openapi_schema':{'components':{'schemas':{'Input':{'properties':{'prompt':{}},'required':['prompt']}}}}}
  def response(path,body=None):
   if path=='/models/google/gemini-2.5-flash':return {'latest_version':version}
   if path=='/predictions':return {'id':'test-id','status':'succeeded','output':['READY']}
   raise AssertionError(path)
  with patch.object(backend,'request',side_effect=response):
   self.assertEqual(backend.predict('google/gemini-2.5-flash',{'prompt':'hello'}),['READY'])
 def test_generation_failure_does_not_end_session_or_hide_overlay(self):
  s=Studio();s.live=True;s.documents={};s.pending_questions=['Why Python?']
  s.panel.show_idle()
  with patch('groq_backend.generate_answer', side_effect=OSError), patch('replicate_backend.ReplicateBackend.predict',side_effect=RuntimeError('synthetic failure')):
   s.generate_pending()
   for _ in range(100):
    APP.processEvents(); QTest.qWait(10)
    if s.paused:break
   self.assertTrue(s.live)
   self.assertTrue(s.paused)
   self.assertTrue(s.panel.isVisible())
   self.assertIn('Session paused',s.panel.reader.toPlainText())
  for worker in s.workers():worker.wait(2000)
  s.close()
if __name__=='__main__':unittest.main()
