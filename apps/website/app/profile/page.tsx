import Brand from '../../components/brand';
import ProfilePanel from '../../components/profile-panel';

export const metadata = { title: 'Your profile · ReplyCue' };

export default function ProfilePage() {
  return <main className="account-page">
    <div className="profile-top">
      <a href="/" aria-label="ReplyCue home"><Brand/></a>
      <a className="button ghost small" href="/">Back to home</a>
    </div>
    <ProfilePanel/>
  </main>;
}
