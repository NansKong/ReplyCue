'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { Bug, Lightbulb, LogIn, MessageCircle, Send } from 'lucide-react';
import { useWebUser } from './web-auth';

const topics = [
  { label: 'Suggestion', icon: Lightbulb },
  { label: 'Sign-in', icon: LogIn },
  { label: 'Installation', icon: Bug },
  { label: 'Other', icon: MessageCircle },
] as const;

const endpoint = 'https://replycue-gateway.vercel.app/api/community';

export default function BetaCommunity() {
  const [count, setCount] = useState<number>();
  const user = useWebUser();
  const [length, setLength] = useState(0);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    fetch(endpoint, options).then(async response => {
      if (!response.ok) return;
      const { connectedAccounts } = await response.json();
      if (!controller.signal.aborted && Number.isSafeInteger(connectedAccounts) && connectedAccounts >= 0) {
        setCount(connectedAccounts);
      }
    }).catch(() => {});
    return () => controller.abort();
  }, []);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || pending) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    setPending(true);
    setStatus('');
    try {
      const token = await user.getIdToken();
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: fields.get('category'), message: fields.get('message') }),
      });
      const result = await response.json();
      if (!response.ok) {
        setStatus(result.error || 'Could not send feedback. Try again shortly.');
        return;
      }
      form.reset();
      setLength(0);
      setStatus('Feedback sent. Thank you for helping improve ReplyCue.');
    } catch {
      setStatus('Could not send feedback. Try again shortly.');
    } finally {
      setPending(false);
    }
  }

  return <section id="feedback" className="section beta-community" aria-labelledby="feedback-title">
    <div className="beta-community-intro">
      <span className="eyebrow">REPLYCUE BETA</span>
      <h2 id="feedback-title">Help improve ReplyCue.</h2>
      <p>Tell us what worked and where you got stuck.</p>
      <div className="beta-count">
        <strong>{count === undefined ? '—' : new Intl.NumberFormat('en').format(count)}</strong>
        <span>{count === undefined ? 'Windows connection count unavailable' : 'Unique accounts connected on Windows since tracking began'}</span>
      </div>
    </div>
    <div className="beta-feedback account-form">
      <form onSubmit={send}>
        <fieldset className="feedback-topics">
          <legend>What’s this about?</legend>
          <div className="feedback-options">
            {topics.map(({ label, icon: Icon }) => <label key={label}>
              <input type="radio" name="category" value={label} defaultChecked={label === 'Suggestion'}/>
              <span><Icon size={16} aria-hidden="true"/>{label}</span>
            </label>)}
          </div>
        </fieldset>
        <label>Your feedback
          <textarea name="message" required minLength={10} maxLength={1500} rows={5}
            placeholder="Tell us what happened or what you’d like to see."
            aria-describedby="feedback-note" onChange={event => setLength(event.currentTarget.value.length)}/>
        </label>
        <div className="feedback-meta">
          <p className="feedback-note" id="feedback-note">Leave out passwords, résumés, and interview transcripts.</p>
          <span aria-hidden="true">{length.toLocaleString('en')} / 1,500</span>
        </div>
        {user?.emailVerified ? <button className="button primary" disabled={pending}>
          <Send size={15} aria-hidden="true"/>{pending ? 'Sending…' : 'Send feedback'}
        </button> : <a className="button ghost" href="/account/">
          {user ? 'Verify your email to send feedback' : 'Sign in to send feedback'}
        </a>}
      </form>
      {status && <p role="status">{status}</p>}
    </div>
  </section>;
}
