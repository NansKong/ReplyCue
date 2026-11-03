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
  s=Studio();s.live=True;s.documents={};s.pending_questions=[]
  class Busy(QThread):
   def run(self):self.msleep(300)
  s.job=Busy();s.job.start();s.panel.reader.setPlainText('Keep this answer.')
  s.fragments=['Why Python?'];s.finish_turn()
  self.assertFalse(s.job.isInterruptionRequested())
  self.assertEqual(s.pending_questions,['Why Python?'])
  self.assertEqual(s.panel.reader.toPlainText(),'Keep this answer.')
  s.fragments=['What about performance?'];s.finish_turn()
  self.assertEqual(s.pending_questions,['Why Python?', 'What about performance?'])
  s.job.wait();s.stop_live();s.close()
 def test_long_question_waits_for_speech_to_finish(self):
  studio=Studio();studio.live=True;studio.speech_active=True
  studio.fragments=['Can you explain']
  with patch.object(studio,'generate_pending'):
   studio.process_audio()
   self.assertEqual(studio.pending_questions,[])
   studio.fragments.append('how caching works?')
   studio.speech_active=False
   studio.process_audio()
   self.assertEqual(studio.pending_questions,['Can you explain how caching works?'])
  studio.stop_live();studio.close()
 def test_new_answer_waits_for_reader(self):
  studio=Studio();studio.live=True
  studio.reader_queue.append(('First?', 'The first answer.'))
  studio.show_next_answer()
  studio.reader_queue.append(('Second?', 'The second answer.'))
  self.assertTrue(studio.reader_hold.isActive())
  self.assertEqual(studio.panel.live_text, 'The first answer.')
  studio.panel.read_after=0
  studio.reader_hold.timeout.emit()
  self.assertEqual(studio.panel.live_text, 'The second answer.')
  studio.stop_live();studio.close()
if __name__=='__main__':unittest.main()
