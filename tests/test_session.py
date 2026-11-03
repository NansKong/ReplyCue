import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import QApplication,Studio,STYLE
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
APP=QApplication.instance() or QApplication([])
APP.setStyleSheet(STYLE)

class SessionTests(unittest.TestCase):
 def test_overlay_incremental_answer_and_setup(self):
  s=Studio(); p=s.panel
  self.assertEqual(s.tabs.count(),4)
  self.assertFalse(hasattr(s,'notes'))
  p.reveal('First sentence.'); QTest.qWait(480)
  p.reveal('First sentence. Second sentence.')
  self.assertEqual(p.reader.toPlainText(),'First sentence. Second sentence.')
  s.close()

 def test_transcription_continues_during_answer(self):
  s=Studio(); s.live=True; s.documents={}
  class Busy(QThread):
   def run(self): self.msleep(400)
  s.job=Busy(); s.job.start()
  with patch('groq_backend.transcribe',return_value='Why Python?'):
   s.audio_turn(b'fake audio')
   for _ in range(100):
    APP.processEvents(); QTest.qWait(10)
    if s.history: break
   self.assertEqual(s.history,['Why Python?'])
   self.assertFalse(s.job.isInterruptionRequested())
   self.assertEqual(s.fragments,['Why Python?'])
   s.pause_session()
   self.assertTrue(s.paused)
   self.assertFalse(s.fragments or s.audio_queue)
  for w in s.workers(): w.wait(2000)
  s.close()

if __name__=='__main__': unittest.main()
