'use client';

import { useEffect, useState } from 'react';
import { getApps, initializeApp } from 'firebase/app';
import {
  browserSessionPersistence, getAuth, GithubAuthProvider, GoogleAuthProvider,
  onAuthStateChanged, setPersistence, signInWithPopup, signOut,
  type Auth, type User,
} from 'firebase/auth';
import Account from './account';

export default function WebAccount() {
  const [auth, setAuth] = useState<Auth>();
  const [user, setUser] = useState<User | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    async function setup() {
      const response = await fetch('/managed-config.json');
      if (!response.ok) throw new Error('Configuration unavailable');
      const { firebaseApiKey } = await response.json();
      if (!firebaseApiKey) throw new Error('Configuration unavailable');
      const app = getApps().find(app => app.name === 'replycue-web') ?? initializeApp({
        apiKey: firebaseApiKey,
        authDomain: 'copilot-teleprompter.firebaseapp.com',
        projectId: 'copilot-teleprompter',
      }, 'replycue-web');
      const instance = getAuth(app);
      await setPersistence(instance, browserSessionPersistence);
      if (!active) return;
      unsubscribe = onAuthStateChanged(instance, setUser);
      setAuth(instance);
    }
    setup().catch(() => {
      if (active) setMessage('Google and GitHub sign-in are unavailable right now.');
    });
    return () => { active = false; unsubscribe?.(); };
  }, []);

  async function social(provider: 'google' | 'github') {
    if (!auth || pending) return;
    setPending(true);
    setMessage('');
    try {
      await signInWithPopup(auth, provider === 'google' ? new GoogleAuthProvider() : new GithubAuthProvider());
    } catch (error) {
      const code = (error as { code?: string }).code;
      setMessage(code === 'auth/account-exists-with-different-credential'
        ? 'An account already uses that email. Sign in with your original method.'
        : code === 'auth/popup-blocked' ? 'Allow pop-ups for ReplyCue and try again.'
        : code === 'auth/popup-closed-by-user' ? 'Sign-in window closed. You can try again.'
        : 'Could not sign in with that provider. Try again or use email.');
    } finally {
      setPending(false);
    }
  }

  return <>
    {user ? <div className="account-actions">
      <p>Signed in{user.email ? ' as ' + user.email : ''}. {user.emailVerified
        ? 'Your account is ready for the upcoming Windows trial.'
        : 'A verified email is required for trial access.'}</p>
      <button className="button ghost small" type="button" disabled={!auth || pending}
        onClick={() => { if (auth) void signOut(auth).catch(() => setMessage('Could not sign out. Try again.')); }}>
        Sign out
      </button>
    </div> : <>
      <div className="account-actions" aria-label="Social sign-in">
        <button className="button ghost small" type="button" disabled={!auth || pending}
          onClick={() => void social('google')}>Continue with Google</button>
        <button className="button ghost small" type="button" disabled={!auth || pending}
          onClick={() => void social('github')}>Continue with GitHub</button>
      </div>
      <Account/>
    </>}
    {message && <p role="status">{message}</p>}
  </>;
}
