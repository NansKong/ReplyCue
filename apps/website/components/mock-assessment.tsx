'use client';
import { useEffect, useState } from 'react';
import { Camera, Check, Code2, ImageOff, LoaderCircle, ScanLine } from 'lucide-react';

type Props = {
  active: boolean; paused: boolean; busy: boolean; connected: boolean;
  command: (action: string, data?: unknown) => Promise<boolean>;
};
export default function MockAssessment({ active, paused, busy, connected, command }: Props) {
  const [image, setImage] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [kind, setKind] = useState('auto');
  const [language, setLanguage] = useState('Python 3');
  useEffect(() => { if (!active) setImage(null); }, [active]);
  async function capture() {
    setError(''); setCapturing(true); setImage(null);
    try {
      const value = await window.copilot?.command('mock-capture') as { image?: string | null } | undefined;
      setImage(value?.image || null);
    } catch { setError('Capture was cancelled or could not complete. Try selecting a region again.'); }
    finally { setCapturing(false); }
  }
  async function solve() {
    setSending(true);
    try { if (await command('mock-solve', { questionType: kind, language })) setImage(null); }
    finally { setSending(false); }
  }
  const disabled = !connected || !active || paused || busy || capturing || sending;
  return <section className="mock-panel" aria-labelledby="mock-title">
    <div className="mock-intro"><span className="note-icon"><ScanLine size={22}/></span><div><h2 id="mock-title">One question. A clear explanation.</h2><p>Capture a coding problem or MCQ from a mock assessment. Review the selected image before sending it.</p></div></div>
    <div className="mock-options"><label>Question type<select value={kind} onChange={e => setKind(e.target.value)} disabled={sending}><option value="auto">Detect automatically</option><option value="coding">Coding problem</option><option value="mcq">Multiple choice</option></select></label><label>Code language<select value={language} onChange={e => setLanguage(e.target.value)} disabled={sending}>{['Python 3', 'JavaScript', 'TypeScript', 'Java', 'C++', 'SQL'].map(item => <option key={item}>{item}</option>)}</select></label></div>
    <div className="mock-capture-area">{image ? <><details className="mock-image-review"><summary>Review selected question</summary><img src={image} alt="Selected mock question. Review all text, options, and constraints before sending."/></details><p><Check size={14}/> Only this selected region will be sent for analysis.</p></> : <><Camera size={32}/><h3>{capturing ? 'Select the question on your screen' : 'Bring the question into focus'}</h3><p>Drag around one question, including its choices, examples, and constraints. Press Esc to cancel. The capture uses the display under your pointer.</p></>}</div>
    <div className="mock-actions"><button className="button ghost" onClick={capture} disabled={disabled}>{capturing ? <LoaderCircle size={16} className="spin"/> : <Camera size={16}/>} {image ? 'Retake capture' : 'Select screen region'}</button>{image ? <><button className="button ghost" disabled={sending || capturing} onClick={() => { setImage(null); void command('mock-discard'); }}><ImageOff size={15}/> Discard</button><button className="button primary" disabled={disabled} onClick={solve}>{sending || busy ? <LoaderCircle className="spin" size={16}/> : <Code2 size={16}/>} Explain & solve</button></> : null}</div>
    <p className="workspace-footnote">{!active ? 'Start a mock session below to capture a question.' : paused ? 'Resume the mock session to continue.' : 'Solutions appear in the floating reader and session history.'} Screenshots stay in memory and are uploaded only when you choose Explain & solve. For mock assessments and permitted assistance.</p>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </section>;
}
