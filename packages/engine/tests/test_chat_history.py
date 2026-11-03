import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import QApplication,Studio
from PySide6.QtTest import QTest
APP=QApplication.instance() or QApplication([])
class ChatHistoryTests(unittest.TestCase):
 def test_history_keeps_pairs_and_does_not_jump(self):
  s=Studio();s.panel.reveal('The current live answer.');QTest.qWait(480)
  s.qa_records=[{'question':f'Question {i}?','answer':'A detailed suggested answer. '*15,'status':'Complete'} for i in range(12)]
  s.refresh_qa();s.panel.toggle_history();APP.processEvents()
  self.assertIn('Question 0?',s.panel.reader.toPlainText())
  self.assertIn('Question 11?',s.qa_view.toPlainText())
  s.panel.reader.verticalScrollBar().setValue(10)
  s.qa_records.append({'question':'New question?','answer':'A new answer.','status':'Complete'})
  s.refresh_qa()
  self.assertEqual(s.panel.reader.verticalScrollBar().value(),10)
  s.panel.reveal('A newer live answer.')
  self.assertNotEqual(s.panel.reader.toPlainText(),'A newer live answer.')
  s.panel.toggle_history()
  self.assertEqual(s.panel.reader.toPlainText(),'A newer live answer.')
  s.close()
 def test_completed_worker_populates_history_and_memory(self):
  s=Studio();s.live=True;s.documents={};s.pending_questions=['What is Python?']
  with patch('groq_backend.generate_answer', side_effect=OSError), patch('replicate_backend.ReplicateBackend.predict',return_value=['Python is a programming language.']):
   s.generate_pending()
   for _ in range(100):
    APP.processEvents();QTest.qWait(10)
    if s.session_memory:break
  self.assertEqual(s.session_memory[0]['question'],'What is Python?')
  self.assertEqual(s.qa_records[0]['status'],'Complete')
  self.assertIn('Python is a programming language.',s.qa_view.toPlainText())
  s.stop_live()
  self.assertTrue(s.qa_records)
  with patch.object(s,'ready',return_value=True),patch.object(s,'start_capture'):
   s.toggle_listen()
   self.assertEqual(s.qa_records,[])
   self.assertFalse(s.qa_view.toPlainText())
   self.assertFalse(s.panel.history_text)
  s.stop_live();s.close()
if __name__=='__main__':unittest.main()
