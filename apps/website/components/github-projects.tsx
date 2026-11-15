'use client';
import { useState } from 'react';
import { FolderGit2, RefreshCw, Check, LoaderCircle, Unplug, ArrowUpRight, Search } from 'lucide-react';
export type GitHubProject = { name:string; url:string; description:string; language:string; fork:boolean; selected?:boolean; syncedAt?:string; files?:string[]; revision?:string };
type Props = { projects:GitHubProject[]; repositories:GitHubProject[]; login:string; githubConnected:boolean; status:string; truncated:boolean; live:boolean; syncing:boolean; connected:boolean; command:(action:string,data?:unknown)=>Promise<boolean> };

export default function GitHubProjects({projects,repositories,login,githubConnected,status,truncated,live,syncing,connected,command}:Props) {
 const [authorizing,setAuthorizing]=useState(false);
 const [pending,setPending]=useState(false);
 const [filter,setFilter]=useState('');
 const disabled=!connected||live||syncing||pending||authorizing;
 const selected=repositories.filter(repo=>repo.selected).length;
 const visible=repositories.filter(repo=>`${repo.name} ${repo.description} ${repo.language}`.toLowerCase().includes(filter.toLowerCase()));
 async function act(action:string,data?:unknown) {
  setPending(true);
  try { await command(action,data); } finally { setPending(false); }
 }
 async function connect() {
  setAuthorizing(true);
  try { await command('github-browser-connect'); } finally { setAuthorizing(false); }
 }
 return <section className="github-projects" aria-labelledby="github-title">
  <div className="github-intro"><span className="note-icon"><FolderGit2 size={23}/></span><div><h2 id="github-title">Your projects. Already connected.</h2><p>Connect GitHub once. ReplyCue automatically finds your public repositories and brings project context into your conversations.</p></div></div>
  <div className={`github-connection ${githubConnected?'is-connected':''}`}>
   <div className="github-account"><span className="github-avatar" aria-hidden="true">{githubConnected?login.charAt(0).toUpperCase():<FolderGit2 size={22}/>}</span><div><strong>{githubConnected?`@${login}`:'Connect your GitHub account'}</strong><p>{githubConnected?'Public repositories · Connected on this PC':'Authorize securely in your browser. No repository links to paste.'}</p></div></div>
   <div className="github-connection-actions">{githubConnected?<><button className="button ghost small" disabled={disabled} onClick={()=>void act('github-refresh')}>{syncing?<LoaderCircle size={15} className="spin"/>:<RefreshCw size={15}/>} Sync projects</button><button className="button ghost small" disabled={disabled} onClick={()=>void connect()}>Reconnect</button><button className="button ghost small" disabled={disabled} onClick={()=>void act('github-disconnect')} aria-label="Disconnect GitHub"><Unplug size={15}/></button></>:<button className="button primary small" disabled={disabled} onClick={()=>void connect()}>{authorizing?<LoaderCircle size={16} className="spin"/>:<FolderGit2 size={17}/>} {authorizing?'Waiting for GitHub…':'Connect GitHub'}<ArrowUpRight size={15}/></button>}</div>
  </div>
  {authorizing&&<div className="github-status" role="status"><LoaderCircle className="spin" size={15}/><span>Finish authorizing GitHub in your browser. Your projects will sync automatically.</span><button className="button ghost small" onClick={()=>void window.copilot?.command('browser-sign-in-cancel')}>Cancel</button></div>}
  {status&&<p className="github-status" role="status">{syncing?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>} {status}</p>}
  {githubConnected&&<div className="github-saved">
   <div className="github-library-header"><div><h3>Public repositories</h3><p>{repositories.length} found · {selected}/10 included in interview context</p></div>{repositories.length>5&&<label className="github-filter"><Search size={15}/><input aria-label="Filter repositories" placeholder="Find a project" value={filter} onChange={e=>setFilter(e.target.value)}/></label>}</div>
   {repositories.length>0&&<p className="github-library-hint">Your most recently updated original projects are selected automatically. Change the selection whenever you need.</p>}
   <div className="github-library">{visible.map(repo=>{const snapshot=projects.find(p=>p.name===repo.name);return <article key={repo.name} className={`github-repo ${repo.selected?'is-selected':''}`}><label className="github-selection"><input type="checkbox" checked={Boolean(repo.selected)} disabled={disabled} onChange={e=>void act('github-toggle',{name:repo.name,selected:e.target.checked})}/><div><h3>{repo.name.split('/').slice(1).join('/')}</h3><p>{repo.description||'No description provided.'}</p><small>{repo.language||'Public repository'}{repo.fork?' · Fork':''}{repo.selected?(snapshot?' · Context ready':syncing?' · Preparing context…':' · Details unavailable; sync to retry'):''}</small></div></label><span className="github-repo-mark" title={snapshot?.syncedAt?`Last synced ${new Date(snapshot.syncedAt).toLocaleString()}`:undefined}>{repo.selected&&snapshot?<Check size={15}/>:<FolderGit2 size={17}/>}</span></article>})}</div>
   {!repositories.length&&!syncing&&<div className="empty-state"><FolderGit2 size={30}/><h3>No public repositories yet.</h3><p>Public projects owned by your connected account will appear here.</p></div>}
   {repositories.length>0&&!visible.length&&<p className="github-library-hint">No projects match your search.</p>}
   {truncated&&<p className="github-library-hint">Showing your 500 most recently pushed public repositories.</p>}
  </div>}
  {!githubConnected&&!authorizing&&<div className="github-benefits"><div><Check size={16}/><span>Automatic repository discovery</span></div><div><Check size={16}/><span>README and technology context</span></div><div><Check size={16}/><span>Public projects only</span></div></div>}
  <p className="workspace-footnote">The connection is encrypted on this PC. Selected project snapshots are saved locally and used in your next session. Relevant context goes to AI only with cloud processing enabled. Repository access does not verify individual contributions.</p>
  {live&&<p className="workspace-footnote">End the current session to update your GitHub connection or project selection.</p>}
 </section>;
}
