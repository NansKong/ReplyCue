import sys,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import QApplication,Studio
from cloud import CloudJob
APP=QApplication.instance() or QApplication([])
class MemoryTests(unittest.TestCase):
 def test_old_turn_retrieved_and_suggestions_separate(self):
  history=['We used PostgreSQL for durable orders.']+['Recent unrelated turn']*10
  memory=[{'question':'Why PostgreSQL?','suggested_answer':'Discuss transaction guarantees.'}]+[{'question':'Other','suggested_answer':'Other suggestion'}]*3
  j=CloudJob('test','model','stt',{},question='Why PostgreSQL?',history=history,session_memory=memory)
  with patch('replicate_backend.ReplicateBackend.predict',return_value=['A complete answer.']) as predict:
   j.run()
  prompt=predict.call_args.args[1]['prompt']
  self.assertIn('PostgreSQL for durable orders',prompt)
  self.assertIn('recent_suggestions_not_spoken',prompt)
  self.assertEqual(j.final_answer,'A complete answer.')
 def test_new_session_resets_memory(self):
  s=Studio();s.session_memory=[{'question':'old','suggested_answer':'old'}];s.history=['old']
  with patch.object(s,'ready',return_value=True),patch.object(s,'start_capture'):
   s.toggle_listen()
   self.assertEqual(s.session_memory,[])
   self.assertEqual(s.history,[])
  s.stop_live();s.close()
if __name__=='__main__':unittest.main()
