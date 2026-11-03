import WebAccount from '../../components/web-account';
import Brand from '../../components/brand';

export default function AccountPage() {
  return <main className="account-page">
    <a href="/" aria-label="ReplyCue home"><Brand/></a>
    <section className="account-card">
      <span className="eyebrow">REPLYCUE BETA</span>
      <h1>Start practicing.</h1>
      <p>Create an account and verify your email to access the Windows trial.</p>
      <WebAccount/>
    </section>
  </main>;
}
