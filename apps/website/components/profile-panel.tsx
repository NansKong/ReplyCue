'use client';

import { useEffect, useState } from 'react';
import { signOut, type User } from '@firebase/auth';
import { ArrowUpRight, UserRound } from 'lucide-react';
import { formatTrialTime } from '../lib/trial-time';
import { getWebAuth, useWebUser } from './web-auth';

type Usage = { unlimited: boolean; trialLimitMs: number | null; remainingTrialMs: number | null;
  trialRunning: boolean; aiEnabled: boolean; trialEnded: boolean; receivedAt: number };
const endpoint = 'https://replycue-gateway.vercel.app/api/community';

function SignedInProfile({ user }: { user: User }) {
  const [usage, setUsage] = useState<Usage>();
  const [now, setNow] = useState(0);
  const [issue, setIssue] = useState('');
  const [signOutError, setSignOutError] = useState('');

  useEffect(() => {
    if (!user.emailVerified) return;
    const controller = new AbortController();
    async function loadUsage() {
      const token = await user.getIdToken();
      const response = await fetch(endpoint, {
        method: 'POST', signal: controller.signal,
        headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'profile' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load usage.');
      if (!controller.signal.aborted) {
        const receivedAt = performance.now();
        setUsage({ ...data, receivedAt });
        setNow(receivedAt);
        setIssue('');
      }
    }
    const refresh = () => loadUsage().catch(error => {
      if (!controller.signal.aborted) setIssue(error instanceof Error ? error.message : 'Could not load usage.');
    });
    refresh();
    const poll = window.setInterval(refresh, 15000);
    return () => { controller.abort(); window.clearInterval(poll); };
  }, [user]);

  useEffect(() => {
    if (!usage?.trialRunning) return;
    const timer = window.setInterval(() => setNow(performance.now()), 1000);
    return () => window.clearInterval(timer);
  }, [usage?.trialRunning]);

  const remainingMs = typeof usage?.remainingTrialMs === 'number'
    ? Math.max(0, usage.remainingTrialMs - (usage.trialRunning ? Math.max(0, now - usage.receivedAt) : 0))
    : 0;
  const providers = user.providerData.map(item => ({
    password: 'Email and password', 'google.com': 'Google', 'github.com': 'GitHub',
  }[item.providerId] ?? 'Other'));
  return <div className="profile-sections">
    <section className="profile-card" aria-labelledby="profile-details">
      <div className="profile-card-head">
        <span className="profile-avatar"><UserRound size={23} aria-hidden="true"/></span>
        <div><h2 id="profile-details">{user.displayName || 'Account details'}</h2><p>{user.email || 'No email on file'}</p></div>
      </div>
      <dl className="profile-rows">
        <div><dt>Email status</dt><dd>{user.emailVerified ? 'Verified' : 'Verification needed'}</dd></div>
        <div><dt>Sign-in methods</dt><dd>{providers.join(', ') || 'Unavailable'}</dd></div>
      </dl>
      <div className="account-actions">
        <a className="button ghost small" href="/account/">Manage account <ArrowUpRight size={14} aria-hidden="true"/></a>
        <button className="button ghost small" onClick={async () => {
          try { await signOut(await getWebAuth()); }
          catch { setSignOutError('Could not sign out. Please try again.'); }
        }}>Sign out</button>
      </div>
      {signOutError && <p role="alert">{signOutError}</p>}
    </section>
    <section className="profile-card" aria-labelledby="profile-usage">
      <h2 id="profile-usage">{usage?.unlimited ? 'AI usage' : 'Trial usage'}</h2>
      {usage ? <>
        {usage.unlimited ? <p className="profile-balance"><strong>Unlimited access</strong></p> : <>
          <p className="profile-balance"><strong>{formatTrialTime(remainingMs)}</strong> remaining</p>
          <progress aria-label="Trial time used" max={usage.trialLimitMs ?? 3600000} value={(usage.trialLimitMs ?? 3600000) - remainingMs}/>
          <p>Your one-hour trial counts active session time. Pausing or ending a session stops the timer.</p>
          {remainingMs === 0 && <p>Your free trial has ended. <a className="text-link" href="#profile-plan">See plan options <ArrowUpRight size={14} aria-hidden="true"/></a></p>}
        </>}
        <p>{usage.aiEnabled ? 'Live transcription and AI answer suggestions are enabled for your account.' : 'Live transcription and suggested answers are temporarily paused.'}</p>
      </> : <p role="status">{!user.emailVerified ? 'Verify your email to view your allowance.' : issue || 'Loading your allowance…'}</p>}
    </section>
    <section className="profile-card" aria-labelledby="profile-plan">
      <h2 id="profile-plan">Plan & subscription</h2>
      <dl className="profile-rows">
        <div><dt>Plan</dt><dd>{usage?.unlimited ? 'Unlimited access' : 'Free trial'}</dd></div>
        <div><dt>Subscription</dt><dd>No active subscription</dd></div>
      </dl>
      <div className="profile-tiers">
        <div><strong>Free trial</strong><p>One hour of active session time.</p></div>
        <div><strong>Pro <span className="tiny-pill">Coming later</span></strong><p>Paid subscriptions aren’t available yet.</p></div>
      </div>
    </section>
  </div>;
}

export default function ProfilePanel() {
  const user = useWebUser();
  return <section className="profile-shell" aria-labelledby="profile-title">
    <span className="eyebrow">ACCOUNT SETTINGS</span>
    <h1 id="profile-title">Your profile</h1>
    {user === undefined ? <p role="status">Loading your account…</p>
      : user ? <SignedInProfile key={user.uid} user={user}/>
      : <div className="profile-card"><p>Sign in to view your profile, plan, and trial allowance.</p>
        <a className="button primary small" href="/account/">Sign in</a>
      </div>}
  </section>;
}
