"""Read-only public GitHub snapshots. Never execute repository content or use login tokens."""
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
    def __init__(self, fetcher=None):
        self.fetcher=fetcher
        self.deadline=time.monotonic()+25

    def get(self, path, optional=False):
        if self.fetcher:
            return self.fetcher(path, optional)
        if time.monotonic()>self.deadline:
            raise GitHubError('GitHub sync timed out. Try syncing again.')
        request=urllib.request.Request('https://api.github.com'+path, headers={
            'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ReplyCue-project-sync'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=min(8,max(.1,self.deadline-time.monotonic()))) as response:
                content=response.read(1200001)
                if len(content)>1200000:raise GitHubError('GitHub returned an oversized response.')
                return json.loads(content)
        except urllib.error.HTTPError as error:
            if optional and error.code==404:return None
            if error.code in (403,429):raise GitHubError('GitHub public API rate limit reached. Wait before syncing again.') from None
            if error.code==404:raise GitHubError('Public repository or user not found. Private repositories are not supported yet.') from None
            raise GitHubError('GitHub could not complete this request. Try again.') from None
        except (OSError, ValueError) as error:
            if isinstance(error,GitHubError):raise
            raise GitHubError('Could not reach GitHub securely. Check your connection.') from None

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
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            self.projects=[p for p in value if isinstance(p,dict) and isinstance(p.get('evidence'),str) and len(p['evidence'])<=32000 and len(parse_target(p['name']))==2][:10]
        except (OSError,ValueError,KeyError,TypeError):self.projects=[]

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.projects,ensure_ascii=False),encoding='utf-8')
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
