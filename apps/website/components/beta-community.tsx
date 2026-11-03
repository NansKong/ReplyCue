'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { getApps, initializeApp } from '@firebase/app';
import { getAuth, onAuthStateChanged, type User } from '@firebase/auth';

const endpoint = 'https://replycue-gateway.vercel.app/api/community';

export default function BetaCommunity() {
  const [count, setCount] = useState<number>();
  const [user, setUser] = useState<User | null>(null);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    let unsubscribe: (() => void) | undefined;
    const options = { signal: controller.signal };
    fetch(endpoint, options).then(async response => {
      if (!response.ok) return;
      const { connectedAccounts } = await response.json();
      if (!controller.signal.aborted && Number.isSafeInteger(connectedAccounts) && connectedAccounts >= 0) {
        setCount(connectedAccounts);
      }
    }).catch(() => {});
    fetch('/managed-config.json', options).then(async response => {
      if (!response.ok) return;
      const config = await response.json();
      const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || config.firebaseApiKey;
      if (!apiKey || controller.signal.aborted) return;
      const app = getApps().find(app => app.name === 'replycue-web') ?? initializeApp({
        apiKey, authDomain: 'copilot-teleprompter.firebaseapp.com', projectId: 'copilot-teleprompter',
      }, 'replycue-web');
      unsubscribe = onAuthStateChanged(getAuth(app), setUser);
    }).catch(() => {});
    return () => { controller.abort(); unsubscribe?.(); };
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
        <label>Topic<select name="category" defaultValue="Suggestion">
          <option>Suggestion</option><option>Sign-in</option><option>Installation</option><option>Other</option>
        </select></label>
        <label>Your feedback<textarea name="message" required minLength={10} maxLength={1500}
          rows={5} placeholder="What should we improve?"/></label>
        <p className="feedback-note">Please leave out passwords, résumés, and interview transcripts.</p>
        {user?.emailVerified ? <button className="button primary" disabled={pending}>
          {pending ? 'Sending…' : 'Send feedback'}
        </button> : <a className="button ghost" href="/account/">Sign in to send feedback</a>}
      </form>
      {status && <p role="status">{status}</p>}
    </div>
  </section>;
}
