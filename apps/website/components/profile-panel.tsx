'use client';

import { useEffect, useState } from 'react';
import { signOut, type User } from '@firebase/auth';
import { ArrowUpRight, UserRound } from 'lucide-react';
import { getWebAuth, useWebUser } from './web-auth';

type Usage = { limitMicroUsd: number; remainingMicroUsd: number; aiEnabled: boolean };
const endpoint = 'https://replycue-gateway.vercel.app/api/community';
const dollars = (micro: number) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 6,
}).format(micro / 1_000_000);

function SignedInProfile({ user }: { user: User }) {
  const [usage, setUsage] = useState<Usage>();
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
      if (!controller.signal.aborted) setUsage(data);
    }
    loadUsage().catch(error => {
      if (!controller.signal.aborted) setIssue(error instanceof Error ? error.message : 'Could not load usage.');
    });
    return () => controller.abort();
  }, [user]);

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
      <h2 id="profile-usage">Trial usage</h2>
      {usage ? <>
        <p className="profile-balance"><strong>{dollars(usage.remainingMicroUsd)}</strong> remaining</p>
        <progress aria-label="Trial allowance used" max={usage.limitMicroUsd} value={usage.limitMicroUsd - usage.remainingMicroUsd}/>
        <p>{dollars(usage.limitMicroUsd - usage.remainingMicroUsd)} used of {dollars(usage.limitMicroUsd)} in included AI usage.</p>
        <p>{usage.aiEnabled ? 'AI usage is enabled for eligible beta accounts.' : 'Live AI usage is paused during the sign-in beta.'}</p>
      </> : <p role="status">{!user.emailVerified ? 'Verify your email to view your allowance.' : issue || 'Loading your allowance…'}</p>}
    </section>
    <section className="profile-card" aria-labelledby="profile-plan">
      <h2 id="profile-plan">Plan & subscription</h2>
      <dl className="profile-rows">
        <div><dt>Plan</dt><dd>Free beta</dd></div>
        <div><dt>Subscription</dt><dd>No active subscription</dd></div>
      </dl>
      <div className="profile-tiers">
        <div><strong>Free beta</strong><p>Account access and a trial allowance.</p></div>
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
