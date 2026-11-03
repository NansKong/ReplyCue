'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Brand from '../../../components/brand';

export default function EmailAction() {
  const [link, setLink] = useState<{ mode: string; code: string }>();
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode');
    const code = params.get('oobCode');
    if (mode && code && ['verifyEmail', 'resetPassword', 'recoverEmail'].includes(mode)) {
      setLink({ mode, code });
    } else {
      setMessage('This link is invalid. Open your account to request a new one.');
    }
  }, []);

  async function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!link || pending) return;
    const form = event.currentTarget;
    setPending(true);
    setMessage('');
    try {
      const config = await fetch('/managed-config.json').then(response => response.json());
      const key = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || config.firebaseApiKey;
      if (!key) throw new Error('Missing configuration');
      const reset = link.mode === 'resetPassword';
      const body = reset
        ? { oobCode: link.code, newPassword: new FormData(form).get('password') }
        : { oobCode: link.code };
      const response = await fetch('https://identitytoolkit.googleapis.com/v1/accounts:' +
        (reset ? 'resetPassword' : 'update') + '?key=' + encodeURIComponent(key), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error('Action failed');
      window.history.replaceState(null, '', '/account/action/');
      setLink(undefined);
      setMessage(reset ? 'Password updated. You can now sign in with your new password.'
        : link.mode === 'recoverEmail' ? 'Your previous email address has been restored.'
        : 'Your email is verified. You can now return to your account.');
    } catch {
      setMessage('This action could not be completed. Try again or request a new link from ReplyCue.');
    } finally {
      setPending(false);
    }
  }

  return <main className="account-page">
    <a href="/" aria-label="ReplyCue home"><Brand/></a>
    <section className="account-card">
      <h1>Manage your account</h1>
      {link && <div className="account-form"><form onSubmit={apply}>
        {link.mode === 'resetPassword' && <label>New password
          <input name="password" type="password" autoComplete="new-password" minLength={8} required/>
        </label>}
        <button className="button primary" disabled={pending}>{pending ? 'Please wait…'
          : link.mode === 'resetPassword' ? 'Save new password'
          : link.mode === 'recoverEmail' ? 'Restore previous email' : 'Verify email'}</button>
      </form></div>}
      {message && <p role="status">{message}</p>}
      <div className="account-actions"><a className="button ghost small" href="/account/">Back to account</a></div>
    </section>
  </main>;
}
