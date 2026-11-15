import sys,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from github_projects import PublicGitHub,GitHubAccount,ProjectStore,GitHubError,plan_repositories
from account_store import AccountStore

TOKEN='gho_'+'x'*36

def row(n,**extra):
 return {'full_name':'owner/project'+str(n),'owner':{'login':'owner'},'private':False,'language':'Python','fork':False,**extra}

class AccountConnectionTests(unittest.TestCase):
 def test_authenticated_pagination_excludes_private_and_other_accounts(self):
  seen=[]
  def api(path,optional):
   seen.append(path)
   if path.endswith('&page=1'):return [row(i) for i in range(100)]
   return [row(100),row(101,private=True),row(102,owner={'login':'other'})]
  repos,truncated=PublicGitHub(api,token=TOKEN).my_repositories('owner')
  self.assertEqual(len(repos),101);self.assertFalse(truncated)
  self.assertEqual(len(seen),2)
  self.assertTrue(all('visibility=public&affiliation=owner' in path for path in seen))

 def test_oversized_account_inventory_is_explicitly_bounded(self):
  repos,truncated=PublicGitHub(lambda path,_:[row(i) for i in range(100)],token=TOKEN).my_repositories('owner')
  self.assertTrue(truncated)
  self.assertLessEqual(len(repos),500)

 def test_default_selection_prefers_original_projects_and_remembers_choices(self):
  rows=[PublicGitHub.summary(row(i,fork=i<4)) for i in range(15)]
  selected=plan_repositories(rows,[])
  self.assertEqual([r['name'] for r in selected if r['selected']],[r['name'] for r in rows[4:14]])
  selected[4]['selected']=False
  selected[14]['selected']=True
  again=plan_repositories(rows,selected)
  self.assertFalse(again[4]['selected']);self.assertTrue(again[14]['selected'])
  self.assertEqual(sum(r['selected'] for r in again),10)

 @unittest.skipUnless(sys.platform=='win32','Windows DPAPI')
 def test_connection_persists_encrypted_and_disconnect_clears_it(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'github-account.dpapi';store=AccountStore(path)
   account=GitHubAccount(store);account.connect(TOKEN,{'login':'owner','id':123})
   self.assertNotIn(TOKEN.encode(),path.read_bytes())
   restored=GitHubAccount(store)
   self.assertEqual(restored.profile,{'login':'owner','id':123});self.assertEqual(restored.token,TOKEN)
   restored.disconnect();self.assertFalse(path.exists());self.assertIsNone(restored.profile)

 def test_auth_header_goes_only_to_fixed_github_host_and_auth_expiry_is_clear(self):
  response=MagicMock();response.__enter__.return_value=response;response.read.return_value=b'{"login":"owner","id":123}'
  opener=MagicMock();opener.open.return_value=response
  with patch('urllib.request.build_opener',return_value=opener):
   client=PublicGitHub(token=TOKEN);self.assertEqual(client.account()['login'],'owner')
   request=opener.open.call_args.args[0]
   self.assertEqual(request.full_url,'https://api.github.com/user')
   self.assertEqual(request.get_header('Authorization'),'Bearer '+TOKEN)
   with self.assertRaises(GitHubError):client.get('//evil.example/user')
   opener.open.side_effect=urllib.error.HTTPError(request.full_url,401,'unauthorized',{},None)
   with self.assertRaisesRegex(GitHubError,'Reconnect GitHub'):client.account()

 def test_legacy_snapshots_migrate_without_credentials_in_project_json(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'projects.json'
   path.write_text(json.dumps([{'name':'owner/project','evidence':'README','selected':True}]))
   store=ProjectStore(path);self.assertEqual(len(store.documents()),1)
   store.catalog=plan_repositories([PublicGitHub.summary(row(1))],[]);store.owner=123;store.save()
   restored=ProjectStore(path);self.assertEqual(len(restored.catalog),1);self.assertEqual(restored.owner,123)
   self.assertNotIn(TOKEN,path.read_text())

class BridgeOAuthTests(unittest.TestCase):
 def test_connect_auto_fetches_projects_then_new_session_uses_them_and_disconnect_clears(self):
  sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'apps'/'windows'/'backend'))
  from bridge import Bridge,DesktopStudio
  from app import QApplication
  from PySide6.QtTest import QTest
  app=QApplication.instance() or QApplication([])
  with tempfile.TemporaryDirectory() as folder:
   store=ProjectStore(Path(folder)/'projects.json')
   store.put({'name':'old/oldrepo','evidence':'Old account private context','selected':True})
   credential_store=MagicMock();credential_store.load.side_effect=OSError()
   account=GitHubAccount(credential_store)
   studio=DesktopStudio()
   def sync(name):return {'name':name,'evidence':'README: Kafka order processing','selected':True,'files':['README.md']}
   with patch('bridge.emit') as emitted,patch('bridge.PublicGitHub') as github,patch.object(studio,'ready',return_value=True),patch.object(studio,'start_capture'),patch('managed_ai.begin_session'),patch('managed_ai.end_session'):
    github.return_value.account.return_value={'id':123,'login':'owner'}
    github.return_value.my_repositories.return_value=([PublicGitHub.summary(row(1)),PublicGitHub.summary(row(2))],False)
    github.return_value.sync.side_effect=sync
    bridge=Bridge(app,studio,store,account)
    bridge.dispatch({'id':1,'action':'github-connect','data':{'githubToken':TOKEN}})
    for _ in range(200):
     app.processEvents();QTest.qWait(10)
     if len(store.projects)==2 and not bridge.github_job.isRunning():break
    self.assertEqual(len(store.projects),2)
    self.assertEqual(bridge.snapshot()['githubLogin'],'owner')
    self.assertNotIn(TOKEN,json.dumps(bridge.snapshot()))
    self.assertNotIn(TOKEN,json.dumps([c.args for c in emitted.call_args_list]))
    self.assertNotIn('old/oldrepo',store.documents())
    bridge.dispatch({'id':2,'action':'start','data':{'resume':'Built order API.','jd':'Kafka role','consent':True}})
    self.assertIn('GitHub owner/project1',studio.documents)
    studio.stop_live()
    bridge.dispatch({'id':3,'action':'github-disconnect'})
    self.assertFalse(store.documents());self.assertFalse(bridge.snapshot()['githubConnected'])
    credential_store.clear.assert_called_once()
    bridge.timer.stop();studio.close()

if __name__=='__main__':unittest.main()
