import sys,base64,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from github_projects import PublicGitHub
from knowledge import answer_context

class DeepProjectTests(unittest.TestCase):
 def test_source_experiment_and_architecture_evidence_are_synced_at_same_revision(self):
  files={'README.md':'Project overview. '*1200,'configs/train.yaml':'base_model: bert-base-uncased\ncorpus_documents: 24000\nvalidation_fraction: 0.2','src/evaluate.py':'metric = "macro_f1"\n# No measured results in this file.','docs/architecture.md':'Encoder outputs feed a linear classifier.','src/server.py':'def predict(text): return model(tokenizer(text))'}
  paths=['configs/train.yaml','src/evaluate.py','docs/architecture.md','src/server.py','.env','secrets.json','vendor/train.py','data/raw.txt','src/key.pem']
  seen=[]
  def api(path,optional):
   seen.append(path)
   if '/commits/' in path:return {'sha':'a'*40}
   if '/git/trees/' in path:return {'tree':[{'path':p,'type':'blob','size':100} for p in paths]}
   if '/readme?' in path:name='README.md'
   elif '/contents/' in path:name=path.split('/contents/')[1].split('?')[0]
   else:return {'full_name':'owner/deepmodel','private':False,'language':'Python','default_branch':'main'}
   if name not in files:return None
   text=files[name].encode();return {'path':name,'size':len(text),'type':'file','encoding':'base64','content':base64.b64encode(text).decode()}
  repo=PublicGitHub(api).sync('owner/deepmodel')
  self.assertIn('configs/train.yaml',repo['files']);self.assertIn('docs/architecture.md',repo['files']);self.assertIn('src/server.py',repo['files'])
  self.assertIn('bert-base-uncased',repo['evidence']);self.assertIn('24000',repo['evidence'])
  self.assertLessEqual(len(repo['evidence']),32000)
  self.assertFalse(any('/contents/'+bad in path for bad in paths[4:] for path in seen))
  self.assertTrue(all('ref='+'a'*40 in path for path in seen if '/contents/' in path or '/readme?' in path))
  context=answer_context('Explain deepmodel base model and corpus size.',{'GitHub owner/deepmodel':repo['evidence'],'GitHub owner/other':'A different BERT experiment using 100 documents.'})
  evidence=context['repository_evidence']
  self.assertEqual(evidence[0]['source'],'GitHub owner/deepmodel')
  self.assertTrue(any('configs/train.yaml' in r['text'] and '24000' in r['text'] for r in evidence))

 def test_later_code_excerpt_retains_its_filename(self):
  docs={'GitHub owner/model':'FILE src/evaluate.py (repository excerpt):\n'+'setup = 0\n'*200+'\n\nmacro_f1 = compute_metric(predictions, labels)'}
  c=answer_context('How is macro_f1 evaluated?',docs)
  self.assertTrue(any('src/evaluate.py' in r['text'] and 'macro_f1' in r['text'] for r in c['repository_evidence']))

 def test_common_word_does_not_exclude_better_project_evidence(self):
  docs={'GitHub owner/model':'Dashboard for the data model.', 'GitHub owner/vision-lab':'FILE src/train.py\nTrain the model with class-weighted cross-entropy.'}
  result=answer_context('How did you train the model?',docs)
  self.assertEqual(result['repository_evidence'][0]['source'],'GitHub owner/vision-lab')

 def test_training_and_evaluation_code_survive_config_competition(self):
  names=['config/main.yaml','config/train.yaml','config/model.yaml','src/train.py','src/evaluate.py','docs/architecture.md','src/app.py','tests/test_model.py']
  tree={'tree':[{'path':name,'type':'blob','size':1000} for name in names]}
  files=PublicGitHub.context_paths(tree)
  self.assertIn('src/train.py',files)
  self.assertIn('src/evaluate.py',files)
  self.assertIn('config/train.yaml',files)

if __name__=='__main__':unittest.main()
