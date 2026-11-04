'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowRight, AudioLines, Check, ChevronRight, FileText, History, Layers, LoaderCircle, Monitor, Pause, Play, Settings2, Square, Upload, X } from 'lucide-react';
import Brand from './brand';
type RecordItem = { question: string; answer: string; status: string };
import Account from './account';
import DesktopProviders from './desktop-providers';

type EngineState = { managed?: boolean; remainingMicroUsd?: number; live: boolean; paused: boolean; busy: boolean; status: string; records: RecordItem[]; transcript: string; configured: boolean; replicateConfigured: boolean; groqConfigured: boolean; model: string; sttModel: string; configPath: string; audioSources: {index:number;name:string}[]; audioLevel:number; audioStatus:string };
type Bridge = { command: (action: string, data?: unknown) => Promise<unknown>; importDocument: () => Promise<string | null>; onState: (callback: (state: EngineState) => void) => () => void };
declare global { interface Window { copilot?: Bridge } }
const tabs = [{key:'resume',label:'Your background',icon:FileText}, {key:'jd',label:'The opportunity',icon:Layers}, {key:'transcript',label:'Live transcript',icon:AudioLines}, {key:'history',label:'Session history',icon:History}] as const;
type Tab = typeof tabs[number]['key'];
const initial: EngineState = {live:false,paused:false,busy:false,status:'Connecting to the local engine…',records:[],transcript:'',configured:false,replicateConfigured:false,groqConfigured:false,model:'',sttModel:'',configPath:'',audioSources:[],audioLevel:0,audioStatus:'Choose the same speaker or headphones as Meet.'};
export default function Workspace() {
  const [state, setState] = useState(initial);
  const [tab, setTab] = useState<Tab>('resume');
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [consent, setConsent] = useState(false);
  const [audioSource, setAudioSource] = useState(-1);
  const [connected, setConnected] = useState(false);
  const [settings, setSettings] = useState(false);
  const [groq, setGroq] = useState('');
  const [replicate, setReplicate] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const modal = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!settings) return;
    const previous = document.activeElement as HTMLElement | null;
    const panel = modal.current;
    const selector = 'button:not(:disabled), input:not(:disabled), a[href], [tabindex="0"]';
    panel?.querySelector<HTMLElement>('input')?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(selector));
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', trap);
    return () => { document.removeEventListener('keydown', trap); previous?.focus(); };
  }, [settings]);
  useEffect(() => {
    const api = window.copilot;
    if (!api) { setState(s => ({...s,status:'Open the Windows app to connect to your local engine.'})); return; }
    setConnected(true);
    const unsubscribe = api.onState(setState);
    api.command('sources').then(value => setState(value as EngineState)).catch(() => setError('Could not connect to the engine. Restart ReplyCue.'));
    return unsubscribe;
  }, []);
  async function command(action: string, data?: unknown) {
    if (!window.copilot) return;
    setPending(true); setError('');
    try { const value = await window.copilot.command(action,data); if (value && typeof value === 'object' && 'records' in value) setState(value as EngineState); return true; }
    catch (e) { setError(e instanceof Error ? e.message.replace(/^Error invoking remote method '[^']+': Error: /,'') : 'Action failed. Try again.'); return false; }
    finally { setPending(false); }
  }
  async function importFile() {
    setError(''); setPending(true);
    try { const text = await window.copilot?.importDocument(); if (text != null) { if(tab === 'resume') setResume(text); else setJd(text); } }
    catch { setError('Could not read this document. Try a text PDF, DOCX, or TXT file.'); }
    finally { setPending(false); }
  }
  const documentTab = tab === 'resume' || tab === 'jd';
  return <main className="workspace-shell">
    <aside className="workspace-sidebar"><Brand/><span className="workspace-label">YOUR WORKSPACE</span><nav aria-label="Workspace">{tabs.map(({key,label,icon:Icon}) => <button key={key} className={tab === key ? 'selected' : ''} onClick={() => setTab(key)} aria-current={tab === key ? 'page' : undefined}><Icon size={17}/>{label}{key === 'history' && state.records.length > 0 ? <span className="count">{state.records.length}</span> : null}</button>)}</nav><div className="sidebar-bottom"><div className="sidebar-message"><span className="status-dot"/><h3>Stay present.</h3><p>Listen first. Let the context help. Answer in your own voice.</p></div><button className="settings-nav" onClick={() => setSettings(true)}><Settings2 size={17}/> Connections <span className={state.configured ? 'connection-dot ready' : 'connection-dot'}/></button><span className="desktop-version"><Monitor size={12}/> Windows preview <span>0.1.10</span></span></div></aside>
    <section className="workspace-main"><header className="workspace-topbar"><span>Workspace <ChevronRight size={13}/> {tabs.find(t => t.key === tab)?.label}</span><span className="tiny-pill"><span className={state.live ? 'status-dot' : 'neutral-dot'}/>{state.live ? state.paused ? 'Session paused' : 'Session active' : 'Ready when you are'}</span></header>
      <div className="workspace-content"><div className="workspace-heading"><div><span className="eyebrow">{documentTab ? 'MAKE IT PERSONAL' : 'THE CURRENT CONVERSATION'}</span><h1>{tab === 'resume' ? 'Résumé & experience' : tab === 'jd' ? 'Know the opportunity.' : tab === 'history' ? 'Keep the whole thread.' : 'Follow the conversation.'}</h1><p>{tab === 'resume' ? 'Import a résumé or paste the experience you want ReplyCue to use.' : tab === 'jd' ? 'Give ReplyCue a sense of the role, the team, and what matters to them.' : tab === 'history' ? 'Every question and suggested answer, together for this session.' : 'Heard playback appears here as the session progresses.'}</p></div></div>
      {!connected ? <div className="notice">This workspace runs inside the Windows app. <a href="/#download">Download ReplyCue <ArrowRight size={14}/></a></div> : null}
      {documentTab ? <div className="document-panel"><div className="document-toolbar"><span>{tab === 'resume' ? <FileText size={16}/> : <Layers size={16}/>} {tab === 'resume' ? 'Résumé & experience' : 'Job description'} <span className="tiny-label">SESSION CONTEXT</span></span><button className="button ghost small" onClick={importFile} disabled={!connected || pending}><Upload size={14}/> Import document</button></div><textarea aria-label={tab === 'resume' ? 'Résumé and experience' : 'Job description'} maxLength={500000} value={tab === 'resume' ? resume : jd} onChange={e => tab === 'resume' ? setResume(e.target.value) : setJd(e.target.value)} placeholder={tab === 'resume' ? 'Paste your résumé, projects, or experience here…' : 'What does this role call for?\n\nPaste the job description here. Your experience and the role’s requirements stay separate.'}/><div className="document-footer"><span>TXT, DOCX or text-based PDF</span><span>{(tab === 'resume' ? resume : jd).trim().split(/\s+/).filter(Boolean).length} words</span></div></div> : <div className="history-panel">{tab === 'history' ? state.records.length ? state.records.map((item,i) => <article className="qa-card" key={i}><div className="qa-meta"><span>QUESTION {String(i+1).padStart(2,'0')}</span><span>{item.status}</span></div><h2>{item.question}</h2><p>{item.answer || 'Preparing a suggestion…'}</p><small>Suggested answer · Not a record of what you said</small></article>) : <div className="empty-state"><History size={34}/><h2>Every thought has a place.</h2><p>Questions and suggestions will appear here.<br/>History stays until you start a new session or close the app.</p></div> : state.transcript ? <div className="transcript-text">{state.transcript}</div> : <div className="empty-state"><AudioLines size={34}/><h2>Ready to listen.</h2><p>Start a session to transcribe your computer’s playback.<br/>This includes audio from other apps.</p></div>}</div>}
      {documentTab ? <div className="context-progress"><span><span className={resume.trim() ? 'step-check done' : 'step-check'}>{resume.trim() ? <Check size={12}/> : '1'}</span> Your background</span><i/><button onClick={() => setTab(tab === 'resume' ? 'jd' : 'resume')}><span className={jd.trim() ? 'step-check done' : 'step-check'}>{jd.trim() ? <Check size={12}/> : '2'}</span>The opportunity <ArrowRight size={13}/></button><small>Optional, but helpful</small></div> : null}
      <div className="audio-routing"><div className="audio-source-row"><label htmlFor="audio-source">Audio source</label><select id="audio-source" value={audioSource} disabled={!connected || state.live || pending} onChange={e => setAudioSource(Number(e.target.value))}><option value={-1}>Windows default speaker</option>{state.audioSources.map(source => <option key={source.index} value={source.index}>{source.name}</option>)}</select><button className="button ghost small" disabled={!connected || state.live || pending} onClick={async () => {setAudioSource(-1);await command('sources');}}>Refresh</button><meter aria-label="Playback signal level" min={0} max={100} value={state.audioLevel}/></div><p>{state.live ? state.audioStatus : 'Match this to Google Meet → Settings → Audio → Speakers. Your microphone is not captured.'}</p></div>
      <div className="session-controls">{!state.live ? <><label className="consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}/><span>Allow cloud processing for this session<small>{state.managed ? 'Audio → Groq · Answer context → Replicate' : 'Audio → Groq · Context → Replicate / Gemini · Provider charges may apply'}</small></span></label><button className="button primary" disabled={!connected || pending || !consent || !state.configured || state.busy} onClick={() => command('start',{resume,jd,consent,audioSource})}>{pending ? <LoaderCircle size={17} className="spin"/> : <Play size={16}/>} Start session <ArrowUpRightIcon/></button></> : <><div className="session-hint"><span className="status-dot"/>{state.paused ? 'Your place is saved. Resume when ready.' : 'Your session is running.'}</div><button className="button ghost" disabled={pending} onClick={() => command('pause')}>{state.paused ? <Play size={14}/> : <Pause size={14}/>} {state.paused ? 'Resume' : 'Pause'}</button><button className="button ghost" disabled={pending} onClick={() => command('end')}><Square size={13}/> End</button><button className="button primary" onClick={() => command('overlay')}>Open reader <ArrowRight size={15}/></button></>}</div>
      <div className="workspace-status" role="status"><span className="neutral-dot"/>{error || state.status}{connected && !state.configured ? <button onClick={() => setSettings(true)}>{state.managed ? 'Sign in' : 'Connect API keys'} <ArrowRight size={13}/></button> : null}</div><p className="workspace-footnote">Session context stays in memory. New sessions clear previous history. {state.live && documentTab ? 'Document edits apply to the next session.' : ''}</p>
      </div>
    </section>
    {settings ? <div className="modal-backdrop" onClick={e => {if(e.target === e.currentTarget) {setSettings(false);setGroq('');setReplicate('');}}}><section ref={modal} className="connection-modal" role="dialog" aria-modal="true" aria-labelledby="connection-title" onKeyDown={e => {if(e.key === 'Escape') {setSettings(false);setGroq('');setReplicate('');}}}><button className="modal-close" aria-label="Close connections" onClick={() => {setSettings(false);setGroq('');setReplicate('');}}><X size={20}/></button><span className="note-icon"><Settings2 size={22}/></span>{state.managed ? <><h2 id="connection-title">Your ReplyCue account</h2>{state.configured ?
      <><p>{typeof state.remainingMicroUsd === 'number' ? `Trial allowance remaining: ${(state.remainingMicroUsd / 1000000).toFixed(4)} USD.` : 'Signed in.'}</p>
      <button className="button ghost" disabled={state.live || pending} onClick={() => command('managed-sign-out')}>Sign out</button></> :
      <Account providers={<DesktopProviders onComplete={() => setSettings(false)}/>} onConnect={async (idToken, refreshToken) => {
        const success = await command('managed-sign-in', { idToken, refreshToken });
        if (success) setSettings(false);
        return Boolean(success);
      }}/>}</> : <><span className="eyebrow">YOUR SERVICES. YOUR KEYS.</span><h2 id="connection-title">Make the connection.</h2><p>Keys are stored in a backend .env file on this computer. Saved keys are never sent back to this screen.</p><form onSubmit={async e => {e.preventDefault(); if(await command('configure',{GROQ_API_KEY:groq,REPLICATE_API_TOKEN:replicate})) {setGroq('');setReplicate('');setSettings(false);}}}><label>Groq <span>{state.groqConfigured ? 'Connected' : 'Transcription'}</span><input autoComplete="off" type="password" placeholder={state.groqConfigured ? 'Leave blank to keep saved key' : 'Enter Groq API key'} value={groq} onChange={e=>setGroq(e.target.value)}/></label><label>Replicate <span>{state.replicateConfigured ? 'Connected' : 'Answer generation'}</span><input autoComplete="off" type="password" placeholder={state.replicateConfigured ? 'Leave blank to keep saved key' : 'Enter Replicate API token'} value={replicate} onChange={e=>setReplicate(e.target.value)}/></label><p className="config-location">{state.configPath || 'Available in the Windows app'}</p>{error ? <p role="alert" className="form-error">{error}</p> : null}<button type="submit" className="button primary" disabled={!connected || pending || state.live || (!groq && !replicate)}>{pending ? 'Saving…' : 'Save connections'}<ArrowRight size={16}/></button>{state.live ? <small>End the session before updating connections.</small> : null}</form></>}</section></div> : null}
  </main>;
}
function ArrowUpRightIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12"/></svg>; }

