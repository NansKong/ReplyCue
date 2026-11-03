import sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import QApplication,Prompter
from cloud import CloudJob
from PySide6.QtTest import QTest
APP=QApplication.instance() or QApplication([])
class ReadingTests(unittest.TestCase):
 def test_new_answer_stays_at_top_for_seven_seconds(self):
  p=Prompter()
  p.reveal('Previous answer. '*100)
  QTest.qWait(500)
  p.timer.stop()
  bar=p.reader.verticalScrollBar()
  bar.setValue(bar.maximum())
  with patch('app.time.monotonic', return_value=100):
   p.reveal('New answer. '*100)
   p.timer.stop()
   p.manual_scroll()
  self.assertEqual(bar.value(),0)
  self.assertEqual(p.read_after,107)
  with patch('app.time.monotonic', return_value=106.9):
   p.scroll()
  self.assertEqual(bar.value(),0)
  with patch('app.time.monotonic', return_value=107.1):
   p.scroll()
  self.assertGreater(bar.value(),0)
  p.close()
 def test_scroll_and_manual_hold(self):
  p=Prompter();text='A readable interview sentence with a useful example. '*80
  p.reveal(text);QTest.qWait(500);p.timer.stop()
  bar=p.reader.verticalScrollBar()
  self.assertEqual(bar.value(),0)
  p.read_after=0
  for _ in range(40):
   p.last_scroll_time=time.monotonic()-.1;p.scroll()
  self.assertGreater(bar.value(),0)
  position=bar.value();p.reveal(text+'Final sentence.');p.timer.stop()
  self.assertEqual(bar.value(),position)
  p.manual_scroll();p.last_scroll_time=time.monotonic()-.1;p.scroll()
  self.assertEqual(bar.value(),position)
  p.auto_read.setChecked(False);p.read_after=0;p.scroll()
  self.assertEqual(bar.value(),position)
  p.close()
 def test_answer_prompt_is_spoken_and_grounded(self):
  j=CloudJob('test','model','stt',{},question='What is computer vision?')
  with patch('replicate_backend.ReplicateBackend.predict',return_value=['A clear answer.']) as run:
   j.run()
  prompt=run.call_args.args[1]['prompt']
  self.assertIn('SAY ALOUD',prompt)
  self.assertIn('Never invent',prompt)
  self.assertIn('one concrete example',prompt)
  self.assertIn('No headings',prompt)
if __name__=='__main__':unittest.main()
