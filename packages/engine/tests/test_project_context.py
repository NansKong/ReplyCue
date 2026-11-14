import sys,json,base64,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from knowledge import answer_context,retrieve
from github_projects import PublicGitHub,ProjectStore,parse_target,GitHubError

class ContextTests(unittest.TestCase):
 def test_later_resume_projects_and_jd_requirements_are_visible(self):
  resume='Project Alpha: frontend dashboards.\n\n'+'Unrelated work. '*350+'\n\nProject Beta: distributed Kafka processing and backpressure.\n\nProject Gamma: computer vision defect detection with OpenCV.'
  jd='Frontend role overview. '*150+'\n\nRequired: Kafka stream processing, backpressure and distributed reliability.'
  context=answer_context('How did you use Kafka and backpressure?',{'Resume':resume,'Job description':jd})
  self.assertTrue(any('Kafka' in x['text'] for x in context['resume_evidence']))
  self.assertTrue(any('backpressure' in x['text'] for x in context['role_evidence']))
  self.assertIn('Project Gamma',context['resume_overview'])
  self.assertIn('Kafka',context['role_requirements'])

 def test_another_project_does_not_retrieve_only_the_previous_project(self):
  c=answer_context('Tell me about another project.',{'Resume':'Project Alpha uses React.\n\nProject Beta uses Kafka.'},['Tell me about your React project.'])
  self.assertIn('Project Beta',c['resume_overview'])
  self.assertFalse(c['resume_evidence'])

 def test_repo_evidence_is_source_separated_and_bounded(self):
  docs={'Resume':'Built only the API layer.','Job description':'Requires leadership.'}
  docs.update({'GitHub owner/project'+str(i):('Repository '+str(i)+'\nKafka architecture. ')*1000 for i in range(10)})
  c=answer_context('Explain Kafka architecture.',docs)
  self.assertEqual(len(c['project_catalog']),10)
  self.assertGreater(len({v['source'] for v in c['repository_evidence']}),1)
  self.assertLessEqual(len(json.dumps(c,ensure_ascii=False,separators=(',',':')).encode()),26000)

 def test_unicode_and_escaped_text_cannot_break_prompt_budget(self):
  c=answer_context('Describe the project.',{'Resume':'\x00\"\\漢'*15000,'Job description':'\"'*18000})
  self.assertLessEqual(len(json.dumps(c,ensure_ascii=False,separators=(',',':')).encode()),26000)

 def test_edited_documents_replace_old_context(self):
  self.assertIn('New Project',answer_context('Explain New Project',{'Resume':'New Project uses Redis.'})['resume_overview'])

class BridgeProjectTests(unittest.TestCase):
 def test_synced_selected_projects_enter_new_session_context(self):
  sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'apps'/'windows'/'backend'))
  from bridge import Bridge,DesktopStudio
  from app import QApplication
  from PySide6.QtTest import QTest
  app=QApplication.instance() or QApplication([])
  with tempfile.TemporaryDirectory() as folder:
   store=ProjectStore(Path(folder)/'projects.json')
   studio=DesktopStudio()
   project={'name':'owner/orders','evidence':'README: Kafka-based order processing.','selected':True,'files':['README.md']}
   with patch('bridge.emit'),patch('bridge.PublicGitHub') as github,patch.object(studio,'ready',return_value=True),patch.object(studio,'start_capture'),patch('managed_ai.begin_session'),patch('managed_ai.end_session'):
    github.return_value.sync.return_value=project
    bridge=Bridge(app,studio,store)
    bridge.dispatch({'id':1,'action':'github-sync','data':{'target':'owner/orders'}})
    for _ in range(100):
     app.processEvents();QTest.qWait(10)
     if store.projects and not bridge.github_job.isRunning():break
    self.assertEqual(store.public()[0]['name'],'owner/orders')
    bridge.dispatch({'id':2,'action':'start','data':{'resume':'Owned the order API.','jd':'Kafka role','consent':True}})
    self.assertIn('GitHub owner/orders',studio.documents)
    self.assertEqual(studio.documents['Resume'],'Owned the order API.')
    self.assertEqual(studio.documents['Job description'],'Kafka role')
    studio.stop_live()
    bridge.dispatch({'id':3,'action':'github-toggle','data':{'name':'owner/orders','selected':False}})
    self.assertFalse(store.documents())
    bridge.timer.stop();studio.close()

class PublicGitHubTests(unittest.TestCase):
 def test_only_fixed_public_github_targets_are_accepted(self):
  self.assertEqual(parse_target('https://github.com/owner/project.git'),['owner','project'])
  for bad in ['http://github.com/owner/repo','https://evil.com/owner/repo','https://github.com@evil.com/owner/repo','https://github.com/owner/repo?token=x','owner/../repo','owner/repo/path']:
   with self.assertRaises(GitHubError):parse_target(bad)

 def test_sync_pins_revision_and_reads_only_supported_files(self):
  seen=[]
  def api(path,optional):
   seen.append(path)
   if '/commits/' in path:return {'sha':'a'*40}
   if '?' not in path:return {'full_name':'owner/project','private':False,'fork':True,'default_branch':'main','description':'Team project','language':'Python'}
   if '/readme?' in path:return {'type':'file','encoding':'base64','size':40,'path':'README.md','content':base64.b64encode(b'Public README. Never execute this content.').decode()}
   return None
  repo=PublicGitHub(api).sync('owner/project')
  self.assertEqual(repo['files'],['README.md'])
  self.assertTrue(repo['fork'])
  self.assertIn('not verified personal work',repo['evidence'])
  self.assertTrue(all('ref='+'a'*40 in path for path in seen if '?' in path))
  self.assertFalse(any('.env' in path for path in seen))
  with tempfile.TemporaryDirectory() as folder:
   store=ProjectStore(Path(folder)/'projects.json');store.put(repo)
   self.assertEqual(len(store.documents()),1)
   self.assertNotIn('evidence',store.public()[0])
   store.projects[0]['selected']=False;store.save()
   self.assertFalse(ProjectStore(store.path).documents())

 def test_private_repository_is_rejected(self):
  with self.assertRaises(GitHubError):PublicGitHub(lambda *a:{'private':True}).sync('owner/private')

if __name__=='__main__':unittest.main()
