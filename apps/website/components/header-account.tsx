'use client';

import { ArrowUpRight, UserRound } from 'lucide-react';
import { useWebUser } from './web-auth';

export default function HeaderAccount() {
  const user = useWebUser();
  return <a className="button small header-account" href="/account/" aria-busy={user === undefined}>
    {user === undefined ? 'Account' : user ? <>
      <span className="profile-mark"><UserRound size={15} aria-hidden="true"/></span> Profile
    </> : <>Sign in <ArrowUpRight size={15} aria-hidden="true"/></>}
  </a>;
}
