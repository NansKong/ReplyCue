'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Pause, Play, SlidersHorizontal } from 'lucide-react';
const examples = [
  { label: 'Explain a concept', question: 'What is computer vision?', answer: 'Computer vision helps software make sense of images and video. For example, a factory can use it to spot defects on a production line. The useful distinction is that it turns visual input into something a system can act on, like a label, a location, or a measurement.' },
  { label: 'Discuss a trade-off', question: 'When would you use a cache?', answer: 'I would use a cache when the same data is read often and fetching it is expensive. For example, caching a product catalogue can reduce database load. The trade-off is freshness, so I would choose an expiry policy based on how quickly the information changes.' },
  { label: 'Follow up naturally', question: 'How would you keep that data fresh?', answer: 'For that catalogue cache, I would start with a short expiry time and invalidate entries when products change. That keeps the implementation simple while limiting stale results. If freshness were critical, I would measure the delay and tighten the invalidation path.' }
];
export default function Demo() {
  const [selected, setSelected] = useState(0);
  const [paused, setPaused] = useState(false);
  const [size, setSize] = useState(20);
  const reader = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = reader.current;
    if (!element || paused) return;
    let started = performance.now();
    const timer = window.setInterval(() => {
      if (performance.now() - started > 2500) element.scrollTop += 1;
    }, 75);
    return () => window.clearInterval(timer);
  }, [paused, selected]);
  const example = examples[selected];
  return <div className="demo" id="demo">
    <div className="demo-topline"><span className="eyebrow">A LITTLE CONTEXT. A LOT MORE CLARITY.</span><span className="tiny-pill">Interactive example</span></div>
    <div className="demo-scene"><div className="scene-grid"/><div className="scene-glow"/><span className="meeting-label">Your conversation, in focus</span>
      <div className="reader-demo">
        <div className="reader-top"><span><span className="status-dot"/> ReplyCue</span><span className="tiny-label">{paused ? 'PAUSED' : 'SAMPLE ANSWER'} <SlidersHorizontal size={13}/></span></div>
        <p className="reader-question">{example.question}</p>
        <div ref={reader} className="demo-answer" style={{ fontSize: size }} key={selected}>{example.answer}</div>
        <div className="reader-bottom"><button className="icon-text" onClick={() => setPaused(!paused)}>{paused ? <Play size={13}/> : <Pause size={13}/>} {paused ? 'Resume preview' : 'Pause preview'}</button><label className="font-control">Aa <input aria-label="Preview text size" type="range" min="16" max="25" value={size} onChange={e => setSize(Number(e.target.value))}/></label></div>
      </div>
      <div className="context-note"><span className="note-icon"><Check size={14}/></span><div>Context stays with you<small>Questions + suggestions, in one session</small></div><ArrowUpRight size={17}/></div>
    </div>
    <div className="demo-tabs" aria-label="Example questions">{examples.map((item, index) => <button key={item.label} aria-pressed={selected === index} onClick={() => { setSelected(index); setPaused(false); }}><span>0{index + 1}</span>{item.label}</button>)}</div>
    <p className="demo-caption">Illustrative responses. This website does not capture audio or call AI services.</p>
  </div>;
}
