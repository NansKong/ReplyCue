import { ArrowDown, ArrowRight, ArrowUpRight, AudioLines, Check, FileText, Layers, Monitor, MoveUpRight } from 'lucide-react';
import Brand from '../components/brand';
import Demo from '../components/demo';
import BetaCommunity from '../components/beta-community';
import HeaderAccount from '../components/header-account';
export default function Home() {
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header"><a href="/" aria-label="ReplyCue home"><Brand/></a><nav aria-label="Main navigation"><a href="#experience">Experience</a><a href="#how-it-works">How it works</a><a href="#questions">Questions</a><a href="#feedback">Feedback</a></nav><HeaderAccount/></header>
    <main id="main">
      <section className="hero"><div className="hero-halo"/><div className="release-label"><span className="status-dot"/> MADE FOR WINDOWS <span className="release-separator"/> EARLY PREVIEW</div>
        <h1>Stay in the<br/>conversation<span className="mint">.</span></h1><p className="hero-copy">Your experience. The right context. A little room to think.<br className="desktop-break"/> Meet the quieter side of interview preparation.</p>
        <div className="hero-actions"><a className="button primary" href="#download"><Monitor size={17} aria-hidden="true"/> Get the Windows beta <ArrowDown size={16} aria-hidden="true"/></a><a className="text-link" href="#demo">Explore the experience <ArrowDown size={16}/></a></div>
        <p className="hero-footnote">Free Windows trial · Verify your email to get started</p>
        <Demo/>
      </section>
      <section id="experience" className="section experience"><div className="section-intro"><span className="eyebrow">LESS FRICTION. MORE PRESENCE.</span><h2>A small window.<br/>A clearer head.</h2><p>Bring the details that make you, you. ReplyCue keeps them close while you focus on the conversation.</p></div>
        <div className="feature-grid"><article className="feature-card context-card"><div className="mini-doc"><FileText size={18}/><span>Your experience</span><Check size={14}/></div><div className="mini-doc offset"><Layers size={18}/><span>The opportunity</span><Check size={14}/></div><div className="feature-copy"><span className="eyebrow">01 / YOUR CONTEXT</span><h3>Start with your story.</h3><p>Add your résumé and the job description. Suggestions draw on your background and the role, without turning requirements into invented experience.</p></div></article>
        <article className="feature-card sound-card"><div className="waveform" aria-hidden="true">{Array.from({length: 34}, (_, i) => <i key={i} style={{height: `${12 + Math.abs(Math.sin(i * .8)) * (i > 8 && i < 26 ? 64 : 22)}px`}}/>)}</div><div className="feature-copy"><span className="eyebrow">02 / FOLLOW THE THOUGHT</span><h3>Listen. Connect. Respond.</h3><p>Playback transcription and concise suggestions work together. Follow-up questions can use context from earlier in the session.</p></div></article>
        <article className="feature-card memory-card"><div className="mini-thread"><span>Earlier in this session</span><div>When would you use a cache?</div><div>How would you keep it fresh? <MoveUpRight size={14}/></div></div><div className="feature-copy"><span className="eyebrow">03 / KEEP YOUR PLACE</span><h3>The thread stays with you.</h3><p>Scroll through questions and suggestions. Return to the live reader when you’re ready, with text size and reading pace under your control.</p></div></article></div>
      </section>
      <section className="workflow section" id="how-it-works"><div><span className="eyebrow">A SIMPLE START</span><h2>Ready in<br/>your own time.</h2><a className="text-link" href="#download">Set up your workspace <ArrowRight size={16}/></a></div><ol>{[['Bring your background','Paste your résumé and role, or import a text PDF, DOCX, or TXT file. Review the extracted text.'],['Create and verify your account','Create an account and verify your email. Sign in to the Windows app to use your trial allowance.'],['Make space for the conversation','Allow cloud processing and start a session. Use the native reader for suggestions, then review the session history.']].map(([title, text], i) => <li key={title}><span className="step-number">0{i+1}</span><div><h3>{title}</h3><p>{text}</p></div></li>)}</ol></section>
      <section className="privacy-strip"><span className="note-icon"><AudioLines size={21}/></span><div><h3>Know what leaves your device.</h3><p>When you enable cloud processing, playback audio and relevant answer context are sent to our AI service.<br/>ReplyCue keeps session history in memory and does not automatically save recordings.</p></div><span className="tiny-pill">You choose when to start</span></section>
      <section className="section faq" id="questions"><div><span className="eyebrow">THE DETAILS</span><h2>A few good<br/>questions.</h2></div><div>{[
        ['Does it work in the browser?', 'The website introduces ReplyCue and lets you try an illustrative reader. Live system-audio capture and the floating reader run in the Windows app.'],
        ['Do I need a subscription?', 'Each verified account gets a one-hour trial for live transcription and suggested answers. It counts active session time across sessions and pauses when you pause or end a session. Paid subscriptions are coming later.'],
        ['What happens to my session?', 'Questions and suggested answers remain available for the current session. Starting a new session or closing the app clears them. They are not saved automatically.'],
        ['Can I use it in an interview?', 'Use assistance where the interviewer or assessment rules permit it. The Windows overlay uses native capture exclusion, but compatibility varies and universal invisibility is not guaranteed.'],
        ['What is included in the Windows preview?', 'You can import your résumé and job description, follow live transcripts and suggested answers in a floating reader, and revisit earlier questions during your session. The preview installer is unsigned.']
      ].map(([q, a]) => <details key={q}><summary>{q}<span aria-hidden="true">+</span></summary><p>{a}</p></details>)}</div></section>
      <section className="download-section" id="download" aria-labelledby="download-title">
        <div className="download-orbit" aria-hidden="true"/>
        <span className="eyebrow">WINDOWS TRIAL BETA</span>
        <h2 id="download-title">Try ReplyCue on Windows.</h2>
        <div className="release-card">
          <div className="release-card-info">
            <span className="note-icon"><Monitor size={21} aria-hidden="true"/></span>
            <div>
              <h3>ReplyCue for Windows</h3>
              <p>Windows x64 · v0.1.13 · Unsigned installer</p>
            </div>
          </div>
          <a className="button primary" href="https://github.com/NansKong/ReplyCue/releases/download/v0.1.13/ReplyCue-Setup-0.1.13.exe">
            Download for Windows <ArrowDown size={16} aria-hidden="true"/>
          </a>
        </div>
        <p>Verify your email to get one hour of active session time for live transcription and suggested answers.</p>
        <a className="text-link" href="/account/">Create a free account <ArrowUpRight size={15} aria-hidden="true"/></a>
      </section>
      <BetaCommunity/>
    </main><footer className="site-footer"><Brand/><span>&copy; 2026 ReplyCue. All rights reserved.</span><a href="#feedback">Feedback</a><a href="#main">Back to top ↑</a></footer>
  </>;
}
