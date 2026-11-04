'use client';

import { ArrowUpRight, UserRound } from 'lucide-react';
import { useWebUser } from './web-auth';

export default function HeaderAccount() {
  const user = useWebUser();
  if (user) return <a className="button ghost profile-link" href="/profile/" aria-label="Open profile" title="Profile">
    <UserRound size={19} aria-hidden="true"/>
  </a>;
  return <a className="button small header-account" href="/account/" aria-busy={user === undefined}>
    {user === undefined ? 'Account' : <>Sign in <ArrowUpRight size={15} aria-hidden="true"/></>}
  </a>;
}
