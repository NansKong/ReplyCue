'use client';
import { useState } from 'react';
import { Camera, LoaderCircle, ScanLine } from 'lucide-react';
type Record = { question: string; answer: string; status: string };
type Props = { active: boolean; paused: boolean; busy: boolean; connected: boolean; watching: boolean; records: Record[];
  language: string; questionType: string; onLanguage: (value: string) => void; onType: (value: string) => void; };
export default function MockAssessment({ active, paused, busy, connected, watching, records, language, questionType, onLanguage, onType }: Props) {
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState('');
  async function capture() {
    setError(''); setCapturing(true);
    try { await window.copilot?.command('mock-capture'); }
    catch (e) { setError(e instanceof Error ? e.message.replace(/^Error invoking remote method '[^']+': Error: /,'') : 'Could not select the question area. Try again.'); }
    finally { setCapturing(false); }
  }
  const latest = records.at(-1);
  return <section className="mock-panel" aria-labelledby="mock-title">
    <div className="mock-intro"><span className="note-icon"><ScanLine size={22}/></span><div><h2 id="mock-title">Select once. Answers follow.</h2><p>Start a mock session and mark the question area. ReplyCue reads new questions there and generates solutions automatically.</p></div></div>
    <div className="mock-options"><label>Question type<select value={questionType} onChange={e => onType(e.target.value)} disabled={active}><option value="auto">Detect automatically</option><option value="coding">Coding problem</option><option value="mcq">Multiple choice</option></select></label><label>Code language<select value={language} onChange={e => onLanguage(e.target.value)} disabled={active}>{['Python 3', 'JavaScript', 'TypeScript', 'Java', 'C++', 'SQL'].map(item => <option key={item}>{item}</option>)}</select></label></div>
    <div className="mock-capture-area mock-auto-state"><ScanLine size={26}/><h3>{capturing ? 'Select the question area' : paused ? 'Screen reading paused' : watching ? busy ? 'Reading the question…' : 'Watching your question area' : 'Ready for automatic screen reading'}</h3><p>{watching ? 'Stable, changed questions are answered automatically. Unchanged questions are not sent again.' : 'When you start, drag around the question and its choices or constraints. No repeated capture or confirmation clicks.'}</p></div>
    <div className="mock-actions"><button className="button ghost" onClick={capture} disabled={!connected || !active || paused || busy || capturing}>{capturing ? <LoaderCircle size={16} className="spin"/> : <Camera size={16}/>} {watching ? 'Change question area' : 'Select question area'}</button></div>
    {latest ? <article className="mock-solution" aria-labelledby="mock-solution-title"><div className="qa-meta"><h3 id="mock-solution-title">Latest solution</h3><span role="status">{latest.status}</span></div><pre>{latest.answer || (latest.status.startsWith('Error') ? 'The request failed. Check the status below, then resume to retry.' : 'Reading the selected question and preparing an explanation…')}</pre></article> : null}
    <p className="workspace-footnote">{!active ? 'Allow cloud processing and start a mock session below.' : 'Answers appear here, in the overlay, and in session history.'} Only the selected area is analyzed. Pause or End stops screen reading and the trial timer. For mock assessments and permitted assistance.</p>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
