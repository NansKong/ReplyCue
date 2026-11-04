'use client';

import { useEffect, useState } from 'react';
import {
  GithubAuthProvider, GoogleAuthProvider,
  onAuthStateChanged, reload, sendEmailVerification, signInWithPopup, signOut,
  createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail,
  type Auth, type User,
} from '@firebase/auth';
import Account from './account';
import { getWebAuth } from './web-auth';

export default function WebAccount() {
  const [auth, setAuth] = useState<Auth>();
  const [user, setUser] = useState<User | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    async function setup() {
      const instance = await getWebAuth();
      if (!active) return;
      unsubscribe = onAuthStateChanged(instance, async current => {
        if (current && !current.emailVerified) await reload(current).catch(() => {});
        if (active && current === instance.currentUser) setUser(current);
      });
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

  async function webEmail(mode: 'login' | 'signup' | 'reset', email: string, password: string) {
    if (!auth) throw new Error('Authentication unavailable');
    const settings = { url: window.location.origin + '/account/' };
    if (mode === 'reset') {
      await sendPasswordResetEmail(auth, email, settings);
      return 'If that email has an account, check your inbox for a reset link.';
    }
    if (mode === 'signup') {
      const { user: created } = await createUserWithEmailAndPassword(auth, email, password);
      await sendEmailVerification(created, settings);
      setMessage('Verification email sent. Check your inbox.');
      return '';
    }
    await signInWithEmailAndPassword(auth, email, password);
    return '';
  }

  async function verifyEmail(checkOnly: boolean) {
    if (!user || pending) return;
    setPending(true);
    try {
      if (checkOnly) {
        await reload(user);
        await user.getIdToken(true);
        setMessage(user.emailVerified ? 'Email verified. Your account is ready.' : 'Still waiting for verification. Open the link in your email first.');
      } else {
        await sendEmailVerification(user, { url: window.location.origin + '/account/' });
        setMessage('Verification email sent. Open the link, then come back and select “I verified my email”.');
      }
    } catch {
      setMessage('Could not complete email verification. Please try again shortly.');
    } finally {
      setPending(false);
    }
  }

  return <>
    {user ? <div className="account-actions">
      <p>Signed in{user.email ? ' as ' + user.email : ''}. {user.emailVerified
        ? 'Your account is ready for the upcoming Windows trial.'
        : 'A verified email is required for trial access.'}</p>
      {!user.emailVerified && user.email && <>
        <button className="button primary small" type="button" disabled={pending}
          onClick={() => void verifyEmail(false)}>Send verification email</button>
        <button className="button ghost small" type="button" disabled={pending}
          onClick={() => void verifyEmail(true)}>I verified my email</button>
      </>}
      <button className="button ghost small" type="button" disabled={!auth || pending}
        onClick={() => { if (auth) void signOut(auth).catch(() => setMessage('Could not sign out. Try again.')); }}>
        Sign out
      </button>
    </div> : <>
      <Account webEmail={webEmail} providers={<div className="account-providers" role="group" aria-label="Other sign-in options">
        <button className="button ghost" type="button" disabled={!auth || pending}
          aria-label="Continue with Google" title="Continue with Google" onClick={() => void social('google')}>
          <svg aria-hidden="true" viewBox="0 0 48 48" width="22" height="22">
            <path fill="#4285F4" d="M43.61 24.46c0-1.36-.12-2.67-.34-3.93H24v7.43h11a9.4 9.4 0 0 1-4.08 6.17v5.14h6.61c3.86-3.56 6.08-8.8 6.08-14.81z"/>
            <path fill="#34A853" d="M24 44c5.51 0 10.13-1.83 13.51-4.73l-6.61-5.14c-1.83 1.23-4.17 1.96-6.9 1.96-5.33 0-9.85-3.6-11.47-8.44H5.71v5.3A20 20 0 0 0 24 44z"/>
            <path fill="#FBBC05" d="M12.53 27.65a12 12 0 0 1 0-7.3v-5.3H5.71a20 20 0 0 0 0 17.9z"/>
            <path fill="#EA4335" d="M24 11.91c3 0 5.7 1.03 7.83 3.06l5.87-5.87C34.13 5.78 29.51 4 24 4A20 20 0 0 0 5.71 15.05l6.82 5.3c1.62-4.84 6.14-8.44 11.47-8.44z"/>
          </svg>
        </button>
        <button className="button ghost" type="button" disabled={!auth || pending}
          aria-label="Continue with GitHub" title="Continue with GitHub" onClick={() => void social('github')}>
          <svg aria-hidden="true" viewBox="0 0 16 16" width="22" height="22" fill="currentColor">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
          </svg>
        </button>
      </div>}/>
    </>}
    {message && <p role="status">{message}</p>}
  </>;
}
