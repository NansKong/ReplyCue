'use client';

import { useEffect, useState } from 'react';
import { getApps, initializeApp } from '@firebase/app';
import { browserSessionPersistence, getAuth, onAuthStateChanged, setPersistence, type Auth, type User } from '@firebase/auth';

let webAuth: Promise<Auth> | undefined;

export function getWebAuth() {
  webAuth ??= (async () => {
    const response = await fetch('/managed-config.json');
    if (!response.ok) throw new Error('Configuration unavailable');
    const config = await response.json();
    const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || config.firebaseApiKey;
    if (!apiKey) throw new Error('Configuration unavailable');
    const app = getApps().find(app => app.name === 'replycue-web') ?? initializeApp({
      apiKey, authDomain: 'copilot-teleprompter.firebaseapp.com', projectId: 'copilot-teleprompter',
    }, 'replycue-web');
    const auth = getAuth(app);
    await setPersistence(auth, browserSessionPersistence);
    return auth;
  })().catch(error => {
    webAuth = undefined;
    throw error;
  });
  return webAuth;
}

export function useWebUser() {
  const [user, setUser] = useState<User | null | undefined>();
  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    getWebAuth().then(auth => {
      if (active) unsubscribe = onAuthStateChanged(auth, setUser);
    }).catch(() => { if (active) setUser(null); });
    return () => { active = false; unsubscribe?.(); };
  }, []);
  return user;
}
