import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ArrowDownToLine, ArrowUp, ChevronDown, Eye, Lightbulb, LoaderCircle, Target, Video, Waves } from 'lucide-react'
import type { Message, Session } from '../types'

const suggestions = ['What should I focus on first?', 'Build me a short drill set', 'How can I improve my breathing?']

export default function Results({ session, analyzing, chatBusy, busy, onChat, onDownload, pendingMessage }: {
  session: Session | null; analyzing: boolean; chatBusy: boolean; busy: boolean
  onChat: (message: string) => Promise<boolean>; onDownload: () => void; pendingMessage: string
}) {
  const [tab, setTab] = useState('priorities')
  const [question, setQuestion] = useState('')
  const chatBottom = useRef<HTMLDivElement>(null)
  const analysis = session?.analysis
  useEffect(() => { if (session?.chat_messages.length || pendingMessage) chatBottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [session?.chat_messages.length, pendingMessage])
  useEffect(() => { setTab('priorities'); setQuestion('') }, [analysis])
  const send = async (text = question) => {
    if (text.trim() && !busy && await onChat(text.trim())) setQuestion('')
  }

  if (analyzing) return <section className="panel results-panel results-solo" aria-live="polite" aria-busy="true">
    <div className="panel-title"><h2>Your analysis</h2><span className="pill cyan"><LoaderCircle size={13} className="spin" /> Analyzing</span></div>
    <div className="analyzing-state"><LoaderCircle size={34} className="spin" />
      <h3>Analyzing footage</h3>
      <p>This can take a minute or two.</p>
    </div>
  </section>

  if (!analysis) return <section className="panel results-panel results-solo empty-results">
    <div className="panel-title"><h2>Your analysis</h2></div>
    <div className="empty-main"><Waves size={34} strokeWidth={1.5} />
      <h3>No analysis yet</h3>
      <p>Upload footage and select Analyze technique.</p>
    </div>
  </section>

  const tabs = [{ id: 'priorities', label: 'Key priorities' }, { id: 'drills', label: 'Your drills' }, { id: 'details', label: 'Details' }]
  const messages: Message[] = [...(session?.chat_messages || []), ...(pendingMessage ? [{ role: 'user' as const, content: pendingMessage }] : [])]
  return <div className="results-stack">
    <section className="panel results-panel">
      <div className="panel-title"><h2>Your analysis</h2><button className="icon-button" title="Download report" aria-label="Download report" disabled={busy} onClick={onDownload}><ArrowDownToLine size={18} /></button></div>
      <div className="analysis-summary">
        <h3>{analysis.stroke_id.label}</h3><span className="confidence">{analysis.stroke_id.confidence_pct}% confidence in stroke / action identification</span>
      </div>
      <div className="result-tabs" role="tablist" aria-label="Analysis sections">{tabs.map((item, index) => <button key={item.id} role="tab" id={`tab-${item.id}`} aria-selected={tab === item.id} aria-controls={`panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => {
        const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : direction ? (index + direction + tabs.length) % tabs.length : -1
        if (next >= 0) { event.preventDefault(); setTab(tabs[next].id); document.getElementById(`tab-${tabs[next].id}`)?.focus() }
      }}>{item.label}{item.id === 'priorities' && <span>{analysis.top_3_priorities.length}</span>}</button>)}</div>
      <div className="result-content" id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {tab === 'priorities' && <div className="priorities">{analysis.top_3_priorities.map((item, index) => <article className="priority" key={index}>
          <div className="priority-heading"><span>0{item.rank}</span><h4>{item.problem}</h4></div><p>{item.likely_cause}</p><div className="coach-cue"><Lightbulb size={17} /><span><small>COACHING CUE</small>{item.cue}</span></div>
        </article>)}</div>}
        {tab === 'drills' && <div className="drill-list">{analysis.drills.map((drill, index) => <article key={index} className="drill"><span className="drill-number">DRILL 0{index + 1}</span><h4>{drill.name}</h4><p>{drill.how}</p><div><Target size={16} /><span>{drill.why}</span></div></article>)}</div>}
        {tab === 'details' && <div className="analysis-details">
          <h4><Eye size={18} /> What’s visible</h4><ul>{analysis.visibility.can_see.map((text, index) => <li key={index}>{text}</li>)}</ul>
          <h4>What this angle can’t tell us</h4><ul>{analysis.visibility.cannot_see.map((text, index) => <li key={index}>{text}</li>)}</ul>
          <h4><Video size={18} /> What to film next</h4>{analysis.what_to_film_next.map((item, index) => <p key={index}><strong>{item.angle}</strong><br />{item.distance}</p>)}
          {(session?.pose_warning || !!session?.pose_metrics.length) && <div className="pose-note"><span className="eyebrow">POSE ESTIMATION · BETA</span><p>These measurements are hints, not definitive technique conclusions.</p>{session.pose_warning && <p>{session.pose_warning}</p>}<ul>{session.pose_metrics.map((text, index) => <li key={index}>{text}</li>)}</ul><div className="pose-frames">{session.annotated_frames.map((url, index) => <img src={url} key={index} alt={`Pose estimation hint, frame ${index + 1}`} />)}</div></div>}
          <details className="raw-data"><summary>Structured analysis <ChevronDown size={15} /></summary><pre>{JSON.stringify(analysis, null, 2)}</pre></details>
        </div>}
      </div>
      <button className="download-bar" onClick={onDownload} disabled={busy}><ArrowDownToLine size={16} /> Download your session report<span>Markdown</span></button>
    </section>
    <section className="panel chat-panel"><div className="chat-title"><Waves size={19} /><h2>Your swim coach</h2></div>
      <div className="chat-messages" role="log" aria-label="Conversation with your swim coach" aria-live="polite">
        {!messages.length && <div className="chat-intro"><p>Ask a follow-up question about this analysis.</p><div className="chat-suggestions">{suggestions.map(text => <button key={text} disabled={busy} onClick={() => void send(text)}>{text}<ArrowUp size={13} /></button>)}</div></div>}
        {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}><span className="message-author">{message.role === 'user' ? 'You' : 'Swim coach'}</span><ReactMarkdown>{message.content}</ReactMarkdown></div>)}
        {chatBusy && <div className="typing-indicator" aria-label="Coach is thinking"><LoaderCircle size={18} className="spin" /></div>}<div ref={chatBottom} />
      </div>
      <form className="chat-input" onSubmit={event => { event.preventDefault(); void send() }}><input aria-label="Ask your coach" placeholder="Ask your coach a question…" value={question} onChange={event => setQuestion(event.target.value)} maxLength={6000} disabled={busy} /><button type="submit" aria-label="Send message" disabled={!question.trim() || busy}>{chatBusy ? <LoaderCircle size={18} className="spin" /> : <ArrowUp size={19} />}</button></form>
      <p className="chat-footnote">Coaching is based on what’s visible in your footage.</p>
    </section>
  </div>
}
