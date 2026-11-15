"""Read-only public GitHub snapshots. Never execute repository content. OAuth tokens are restricted to the GitHub API."""
import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

class GitHubError(ValueError):
    pass

class GitHubAuthorizationError(GitHubError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise GitHubError('GitHub redirected this request. Use the current repository address.')


def parse_target(value):
    if not isinstance(value,str) or len(value)>300:
        raise GitHubError('Enter a GitHub username or public repository URL.')
    value=value.strip()
    if '://' in value:
        parsed=urllib.parse.urlsplit(value)
        if parsed.scheme!='https' or parsed.netloc.lower()!='github.com' or parsed.query or parsed.fragment:
            raise GitHubError('Use an https://github.com/owner/repository URL.')
        value=parsed.path.strip('/')
    value=value.removesuffix('.git')
    parts=value.split('/')
    if len(parts) not in (1,2) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})',parts[0]):
        raise GitHubError('Enter a valid GitHub username or owner/repository.')
    if len(parts)==2 and not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',parts[1]):
        raise GitHubError('Enter a valid repository name.')
    if any(p in ('.','..') for p in parts):
        raise GitHubError('Invalid repository address.')
    return parts


class PublicGitHub:
    def __init__(self, fetcher=None, token=None):
        self.fetcher=fetcher
        self.token=token
        self.deadline=time.monotonic()+25

    def get(self, path, optional=False):
        if self.fetcher:
            return self.fetcher(path, optional)
        if time.monotonic()>self.deadline:
            raise GitHubError('GitHub sync timed out. Try syncing again.')
        if not isinstance(path,str) or not path.startswith('/') or path.startswith('//'):
            raise GitHubError('Invalid GitHub API path.')
        headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ReplyCue-project-sync'}
        if self.token:headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request('https://api.github.com'+path, headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=min(8,max(.1,self.deadline-time.monotonic()))) as response:
                content=response.read(1200001)
                if len(content)>1200000:raise GitHubError('GitHub returned an oversized response.')
                return json.loads(content)
        except urllib.error.HTTPError as error:
            if optional and error.code==404:return None
            if error.code==401:raise GitHubAuthorizationError('GitHub authorization expired or was revoked. Reconnect GitHub.') from None
            if error.code==429 or (error.code==403 and (error.headers.get('X-RateLimit-Remaining')=='0' or error.headers.get('Retry-After'))):
                raise GitHubError('GitHub rate limit reached. Wait a few minutes before refreshing projects.') from None
            if error.code==403:raise GitHubError('GitHub refused access. Reconnect GitHub or try again later.') from None
            if error.code==404:raise GitHubError('Public repository or user not found. Private repositories are not supported yet.') from None
            raise GitHubError('GitHub could not complete this request. Try again.') from None
        except (OSError, ValueError) as error:
            if isinstance(error,GitHubError):raise
            raise GitHubError('Could not reach GitHub securely. Check your connection.') from None

    def account(self):
        row=self.get('/user')
        login=row.get('login')
        if len(parse_target(login))!=1 or type(row.get('id')) is not int:
            raise GitHubError('GitHub did not return a valid account.')
        return {'login':login,'id':row['id']}

    def my_repositories(self, login):
        """Paginate the authenticated user's public, owned repositories (bounded at 500)."""
        parse_target(login)
        repos={}
        truncated=False
        for page in range(1,7):
            rows=self.get('/user/repos?visibility=public&affiliation=owner&sort=pushed&per_page=100&page='+str(page))
            if not isinstance(rows,list):raise GitHubError('Invalid GitHub repository list.')
            if page==6:
                truncated=bool(rows)
                break
            for row in rows:
                if row.get('private') is not False or str((row.get('owner') or {}).get('login','')).lower()!=login.lower():continue
                summary=self.summary(row)
                repos[summary['name'].lower()]=summary
            if len(rows)<100:break
        return list(repos.values()),truncated

    def listing(self,target):
        parts=parse_target(target)
        if len(parts)==2:
            rows=[self.get('/repos/'+'/'.join(parts))]
        else:
            rows=self.get('/users/'+parts[0]+'/repos?per_page=100&sort=updated&type=owner')
        return [self.summary(row) for row in rows if not row.get('private')][:100]

    @staticmethod
    def summary(row):
        name=row.get('full_name','')
        if len(parse_target(name))!=2:raise GitHubError('Invalid repository response.')
        return {'name':name,'url':'https://github.com/'+name,'description':str(row.get('description') or '')[:600],
                'language':str(row.get('language') or ''),'fork':bool(row.get('fork'))}

    def sync(self,target):
        parts=parse_target(target)
        if len(parts)!=2:raise GitHubError('Choose a public repository to sync.')
        path='/repos/'+'/'.join(parts)
        row=self.get(path)
        if row.get('private'):raise GitHubError('Only public repositories are supported.')
        result=self.summary(row)
        branch=row.get('default_branch','main')
        revision=self.get(path+'/commits/'+urllib.parse.quote(branch,safe=''),optional=True)
        sha=(revision or {}).get('sha')
        ref=sha if isinstance(sha,str) and re.fullmatch(r'[a-fA-F0-9]{40,64}',sha) else branch
        result['revision']=ref
        result['syncedAt']=datetime.now(timezone.utc).isoformat()
        result['selected']=True
        evidence=['Public repository: '+result['name'], 'Description: '+result['description'],
                  'Primary language: '+result['language'], 'Fork: '+str(result['fork']), 'Revision: '+ref]
        files=[]
        manifests={'Python':['pyproject.toml','requirements.txt'],'JavaScript':['package.json'],'TypeScript':['package.json'],'Rust':['Cargo.toml'],'Go':['go.mod'],'Java':['pom.xml']}
        for name in ['README']+manifests.get(result['language'],[]):
            endpoint=path+'/readme' if name=='README' else path+'/contents/'+name
            doc=self.get(endpoint+'?ref='+urllib.parse.quote(ref,safe=''),optional=True)
            if not doc or doc.get('type') not in (None,'file') or doc.get('encoding')!='base64':continue
            if not isinstance(doc.get('size'),int) or doc['size']>100000:continue
            try:text=base64.b64decode(doc['content'],validate=False).decode('utf-8')
            except (ValueError,UnicodeError,KeyError):continue
            if '\x00' in text:continue
            file_name=str(doc.get('path') or name)
            limit=18000 if name=='README' else 4000
            evidence.append('FILE '+file_name+' (repository evidence, not verified personal work):\n'+text[:limit])
            files.append(file_name)
            if len(files)>=4:break
        result['files']=files
        result['evidence']='\n\n'.join(evidence)[:32000]
        return result


class ProjectStore:
    def __init__(self,path):
        self.path=Path(path)
        self.catalog=[]
        self.owner=None
        self.truncated=False
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value,dict):
                catalog=value.get('catalog',[])
                self.catalog=[p for p in catalog[:500] if isinstance(p,dict) and len(parse_target(p.get('name')))==2] if isinstance(catalog,list) else []
                self.owner=value.get('owner')
                self.truncated=value.get('truncated') is True
                value=value.get('projects',[])
            self.projects=[p for p in value if isinstance(p,dict) and isinstance(p.get('evidence'),str) and len(p['evidence'])<=32000 and len(parse_target(p['name']))==2][:10]
        except (OSError,ValueError,KeyError,TypeError):
            self.projects=[]
            self.catalog=[]
            self.owner=None

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps({'projects':self.projects,'catalog':self.catalog,'owner':self.owner,'truncated':self.truncated},ensure_ascii=False),encoding='utf-8')
        temp.replace(self.path)

    def put(self,project):
        old=next((p for p in self.projects if p['name'].lower()==project['name'].lower()),None)
        if old:project['selected']=old.get('selected',True)
        else:
            if len(self.projects)>=10:raise GitHubError('You can keep up to 10 projects. Remove one before adding another.')
        self.projects=[p for p in self.projects if p is not old]+[project]
        self.save()

    def public(self):
        return [{k:v for k,v in p.items() if k!='evidence'} for p in self.projects]

    def documents(self):
        return {'GitHub '+p['name']:p['evidence'] for p in self.projects if p.get('selected')}

    def clear(self):
        self.projects=[]
        self.catalog=[]
        self.owner=None
        self.truncated=False
        self.save()


def plan_repositories(rows, previous):
    """Auto-select recent original projects on first connection; retain explicit choices later."""
    previous_names={r['name'].lower():r.get('selected',False) for r in previous}
    defaults={r['name'].lower() for r in sorted(rows,key=lambda r:r['fork'])[:10]} if not previous else set()
    result=[]
    selected=0
    for row in rows:
        row=dict(row)
        row['selected']=bool(previous_names.get(row['name'].lower(),row['name'].lower() in defaults)) and selected<10
        selected+=row['selected']
        result.append(row)
    return result


class GitHubAccount:
    """The OAuth credential is persisted only in the native DPAPI store, never in project JSON."""
    def __init__(self, store=None):
        self.store=store
        self.token=None
        self.profile=None
        if store:
            try:
                value=json.loads(store.load() or '{}')
                self.validate_token(value.get('token'))
                profile=value['profile']
                if len(parse_target(profile.get('login')))!=1 or type(profile.get('id')) is not int:raise ValueError()
                self.token=value['token']
                self.profile={'login':profile['login'],'id':profile['id']}
            except (OSError,ValueError,KeyError,TypeError):pass

    @staticmethod
    def validate_token(token):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_]{20,512}',token):
            raise GitHubError('Invalid GitHub authorization. Reconnect GitHub from ReplyCue.')

    def connect(self, token, profile):
        self.validate_token(token)
        if not self.store:raise GitHubError('Secure GitHub credential storage is unavailable. Restart ReplyCue.')
        self.store.save(json.dumps({'token':token,'profile':profile}))
        self.token,self.profile=token,profile

    def disconnect(self):
        if self.store:self.store.clear()
        self.token,self.profile=None,None
