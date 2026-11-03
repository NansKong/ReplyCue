import sys,io,wave,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import QApplication
from cloud import CloudJob,answer_is_complete
from groq_backend import prepare_audio
APP=QApplication.instance() or QApplication([])
class CompletionTests(unittest.TestCase):
 def test_cut_answer_is_repaired_once(self):
  job=CloudJob('test','model','stt',{},question='What is computer vision?')
  with patch('replicate_backend.ReplicateBackend.predict',side_effect=[['For example, a quality-'],['Computer vision interprets images. It can detect defects. The right approach depends on the task.']]) as predict:
   job.run()
  self.assertEqual(predict.call_count,2)
  self.assertTrue(answer_is_complete(job.final_answer))
 def test_repeated_truncation_is_not_silent(self):
  job=CloudJob('test','model','stt',{},question='Explain this.')
  errors=[];job.problem.connect(errors.append)
  with patch('replicate_backend.ReplicateBackend.predict',return_value=['An unfinished fragment']):job.run()
  self.assertFalse(job.final_answer)
  self.assertIn('incomplete response twice',errors[0])
 def test_stereo_audio_is_compact_mono_16k(self):
  out=io.BytesIO()
  with wave.open(out,'wb') as wav:
   wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000);wav.writeframes(b'\0'*192000)
  original=out.getvalue();compact=prepare_audio(original)
  with wave.open(io.BytesIO(compact),'rb') as wav:
   self.assertEqual((wav.getnchannels(),wav.getframerate(),wav.getsampwidth()),(1,16000,2))
   self.assertAlmostEqual(wav.getnframes()/16000,1,places=2)
  self.assertLess(len(compact),len(original)/5)
if __name__=='__main__':unittest.main()
