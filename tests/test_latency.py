import io,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replicate_backend import ReplicateBackend
from app import QApplication,Studio
from PySide6.QtCore import QThread
APP=QApplication.instance() or QApplication([])
class LatencyTests(unittest.TestCase):
 def test_stream_preserves_spaces_and_multiline(self):
  b=ReplicateBackend('test',lambda:False);updates=[]
  raw=b'event: output\ndata: Hello \n\nevent: output\ndata: world.\n\nevent: done\ndata: {}\n\n'
  with patch('replicate_backend.urllib.request.urlopen',return_value=io.BytesIO(raw)):
   b.consume_stream('https://stream.replicate.com/test',updates.append,time.monotonic()+10)
  self.assertEqual(updates,['Hello ','Hello world.'])
 def test_fragment_does_not_cancel_answer_or_erase_text(self):
  s=Studio();s.live=True;s.documents={};s.pending_question=''
  class Busy(QThread):
   def run(self):self.msleep(300)
  s.job=Busy();s.job.start();s.panel.reader.setPlainText('Keep this answer.')
  s.fragments=['Why Python?'];s.finish_turn()
  self.assertFalse(s.job.isInterruptionRequested())
  self.assertEqual(s.pending_question,'Why Python?')
  self.assertEqual(s.panel.reader.toPlainText(),'Keep this answer.')
  s.fragments=['What about performance?'];s.finish_turn()
  self.assertIn('Why Python?',s.pending_question)
  self.assertIn('What about performance?',s.pending_question)
  s.job.wait();s.stop_live();s.close()
if __name__=='__main__':unittest.main()
