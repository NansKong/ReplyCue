import WebAccount from '../../components/web-account';
import Brand from '../../components/brand';

export default function AccountPage() {
  return <main className="account-page">
    <a href="/" aria-label="ReplyCue home"><Brand/></a>
    <section className="account-card">
      <span className="eyebrow">YOUR REPLYCUE ACCOUNT</span>
      <h1>Your next conversation starts here.</h1>
      <p>Create an account and verify your email to access the Windows trial.</p>
      <WebAccount/>
      <div className="account-actions"><a className="button ghost small" href="/">← Back to home</a></div>
    </section>
  </main>;
}
