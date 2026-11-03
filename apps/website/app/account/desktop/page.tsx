'use client';

import { useEffect, useState } from 'react';
import { getApps, initializeApp } from '@firebase/app';
import { getAuth, GithubAuthProvider, GoogleAuthProvider, inMemoryPersistence,
  setPersistence, signInWithPopup, signOut, type Auth } from '@firebase/auth';
import Brand from '../../../components/brand';

type Handoff = { provider: 'google' | 'github'; port: number; nonce: string };

export default function DesktopSignIn() {
  const [handoff, setHandoff] = useState<Handoff>();
  const [auth, setAuth] = useState<Auth>();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    async function setup() {
      const values = new URLSearchParams(window.location.hash.slice(1));
      const provider = values.get('provider');
      const port = Number(values.get('port'));
      const nonce = values.get('nonce');
      if ((provider !== 'google' && provider !== 'github') || !Number.isInteger(port) ||
          port < 1024 || port > 65535 || !nonce || !/^[0-9a-f]{64}$/.test(nonce)) {
        throw new Error('Invalid handoff');
      }
      const response = await fetch('/managed-config.json');
      const config = await response.json();
      const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || config.firebaseApiKey;
      if (!apiKey) throw new Error('Missing Firebase configuration');
      const app = getApps().find(app => app.name === 'replycue-desktop-handoff') ??
        initializeApp({ apiKey, authDomain: 'copilot-teleprompter.firebaseapp.com',
          projectId: 'copilot-teleprompter' }, 'replycue-desktop-handoff');
      const instance = getAuth(app);
      await setPersistence(instance, inMemoryPersistence);
      if (active) {
        setHandoff({ provider, port, nonce });
        setAuth(instance);
      }
    }
    setup().catch(() => {
      if (active) setMessage('Open sign-in from ReplyCue for Windows to start a new connection.');
    });
    return () => { active = false; };
  }, []);

  async function signIn() {
    if (!auth || !handoff || pending) return;
    setPending(true);
    setMessage('');
    try {
      const { user } = await signInWithPopup(auth, handoff.provider === 'google'
        ? new GoogleAuthProvider() : new GithubAuthProvider());
      if (!user.emailVerified) {
        await signOut(auth);
        setMessage('Verify your email in your ReplyCue web account, then try again from Windows.');
        return;
      }
      const idToken = await user.getIdToken();
      const refreshToken = user.refreshToken;
      // Form navigation delivers the session to the one-time loopback listener.
      // Credentials travel in the request body, never in the address bar.
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = 'http://127.0.0.1:' + handoff.port + '/replycue/' + handoff.nonce;
      for (const [name, value] of Object.entries({ idToken, refreshToken })) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        form.append(input);
      }
      document.body.append(form);
      form.submit();
    } catch {
      setMessage('Could not complete browser sign-in. Try again or use email in ReplyCue.');
    } finally {
      setPending(false);
    }
  }

  return <main className="account-page">
    <a href="/" aria-label="ReplyCue home"><Brand/></a>
    <section className="account-card">
      <h1>Sign in to ReplyCue</h1>
      <p>Connect your account to ReplyCue for Windows.</p>
      {handoff && <button className="button primary" type="button" disabled={!auth || pending}
        onClick={() => void signIn()}>
        {pending ? 'Connecting…' : handoff.provider === 'google' ? 'Continue with Google' : 'Continue with GitHub'}
      </button>}
      {message && <p role="status">{message}</p>}
      <div className="account-actions"><a className="button ghost small" href="/account/">Open web account</a></div>
    </section>
  </main>;
}
