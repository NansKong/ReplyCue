'use client';
import { useState, type FormEvent, type ReactNode } from 'react';

export default function Account({ onConnect, providers }: {
  providers?: ReactNode;
  onConnect?: (idToken: string, refreshToken: string) => Promise<boolean>;
}) {
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>('login');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setPending(true);
    setMessage('');
    try {
      const config = await fetch('/managed-config.json').then(r => r.json());
      const firebaseApiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || config.firebaseApiKey;
      if (!firebaseApiKey) {
        setMessage('Account access has not been configured yet.');
        return;
      }
      async function auth(action: string, data: object) {
        const result = await fetch(
          'https://identitytoolkit.googleapis.com/v1/accounts:' + action + '?key=' +
          encodeURIComponent(firebaseApiKey), {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          },
        );
        if (!result.ok) throw new Error('Authentication failed');
        return result.json();
      }
      const email = fields.get('email');
      if (mode === 'reset') {
        await auth('sendOobCode', { requestType: 'PASSWORD_RESET', email });
        setMessage('If that email has an account, check your inbox for a reset link.');
        return;
      }
      const session = await auth(mode === 'signup' ? 'signUp' : 'signInWithPassword', {
        email, password: fields.get('password'), returnSecureToken: true,
      });
      const profile = await auth('lookup', { idToken: session.idToken });
      if (!profile.users?.[0]?.emailVerified) {
        await auth('sendOobCode', { requestType: 'VERIFY_EMAIL', idToken: session.idToken });
        setMessage('Check your inbox to verify your email, then sign in again.');
        setMode('login');
      } else if (onConnect) {
        const connected = await onConnect(session.idToken, session.refreshToken);
        setMessage(connected ? 'Connected. You can start a practice session.' : 'Could not connect to managed AI.');
      } else {
        setMessage('Email verified. Your account is ready for the upcoming Windows trial.');
      }
      form.reset();
    } catch {
      setMessage(mode === 'reset'
        ? 'If that email has an account, check your inbox for a reset link.'
        : 'Could not continue. Check your details and try again.');
    } finally {
      setPending(false);
    }
  }

  return <div className="account-form">
    <form onSubmit={submit}>
      <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254}/></label>
      {mode !== 'reset' && <label>Password<input name="password" type="password" required
        minLength={mode === 'signup' ? 8 : undefined} maxLength={256}
        autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}/></label>}
      <button className="button primary" disabled={pending}>
        {pending ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}
      </button>
      {mode === 'login' && providers}
    </form>
    <div className="account-actions">
      {mode !== 'login' && <button className="button ghost small" onClick={() => setMode('login')}>Sign in</button>}
      {mode !== 'signup' && <button className="button ghost small" onClick={() => setMode('signup')}>Create an account</button>}
      {mode !== 'reset' && <button className="button ghost small" onClick={() => setMode('reset')}>Reset password</button>}
    </div>
    <p role="status" aria-live="polite">{message}</p>
  </div>;
}
