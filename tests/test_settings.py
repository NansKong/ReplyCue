import sys,unittest,tempfile,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import settings
from app import QApplication,Studio
APP=QApplication.instance() or QApplication([])
class ConfigurationTests(unittest.TestCase):
 def test_env_edits_take_effect_without_restart(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'.env'
   path.write_text('REPLICATE_API_TOKEN=first\nGROQ_API_KEY=first-groq\n')
   with patch.object(settings,'ENV_PATH',path),patch.dict(os.environ,{},clear=True):
    self.assertEqual(settings.configuration()[0],'first')
    path.write_text('REPLICATE_API_TOKEN=second\nGROQ_API_KEY=second-groq\n')
    self.assertEqual(settings.configuration()[0],'second')
    self.assertEqual(settings.configuration()[3],'second-groq')
 def test_consent_is_not_reported_as_missing_keys(self):
  s=Studio()
  with patch('app.configuration',return_value=('test-token','model','stt','test-groq')),patch.object(s.panel,'ensure_protection',return_value=True):
   self.assertFalse(s.ready())
   self.assertIn('Both API keys are loaded',s.status.text())
   s.consent.setChecked(True)
   self.assertTrue(s.ready())
  s.close()
 def test_missing_key_is_named(self):
  s=Studio()
  with patch('app.configuration',return_value=('test-token','model','stt','')):
   self.assertFalse(s.ready())
   self.assertIn('Missing GROQ_API_KEY',s.status.text())
   self.assertNotIn('test-token',s.status.text())
  s.close()
if __name__=='__main__':unittest.main()
