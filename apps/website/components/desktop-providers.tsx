'use client';

import { useEffect, useState } from 'react';

export default function DesktopProviders({ onComplete }: { onComplete: () => void }) {
  const [waiting, setWaiting] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => () => {
    void window.copilot?.command('browser-sign-in-cancel').catch(() => {});
  }, []);

  async function open(provider: 'google' | 'github') {
    const bridge = window.copilot;
    if (!bridge || waiting) return;
    setWaiting(true);
    setMessage('Complete sign-in in your browser, then return to ReplyCue.');
    try {
      await bridge.command('browser-sign-in', { provider });
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Browser sign-in could not be completed.');
    } finally {
      setWaiting(false);
    }
  }

  return <div className="desktop-providers">
    <button type="button" className="button ghost" disabled={waiting}
      onClick={() => void open('google')}>Continue with Google</button>
    <button type="button" className="button ghost" disabled={waiting}
      onClick={() => void open('github')}>Continue with GitHub</button>
    {waiting && <button type="button" className="button ghost small"
      onClick={() => void window.copilot?.command('browser-sign-in-cancel')}>Cancel browser sign-in</button>}
    {message && <p role="status">{message}</p>}
    <span className="desktop-sign-in-divider">or use email</span>
  </div>;
}
