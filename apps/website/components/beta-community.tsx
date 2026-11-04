'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { ChevronDown, Send } from 'lucide-react';
import { useWebUser } from './web-auth';

const topics = ['Suggestion', 'Sign-in', 'Installation', 'Other'];

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
      const { registeredAccounts } = await response.json();
      if (!controller.signal.aborted && Number.isSafeInteger(registeredAccounts) && registeredAccounts >= 0) {
        setCount(registeredAccounts);
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
        <strong>{count === undefined ? '—' : count >= 10 ? '10+' : count}</strong>
        <span>{count === undefined ? 'Account count unavailable' : 'People who’ve joined ReplyCue'}</span>
      </div>
    </div>
    <div className="beta-feedback account-form">
      <form onSubmit={send}>
        <label htmlFor="feedback-topic">What’s this about?
          <span className="feedback-select">
            <select id="feedback-topic" name="category" defaultValue="Suggestion">
              {topics.map(topic => <option key={topic} value={topic}>{topic}</option>)}
            </select>
            <ChevronDown size={18} aria-hidden="true"/>
          </span>
        </label>
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
