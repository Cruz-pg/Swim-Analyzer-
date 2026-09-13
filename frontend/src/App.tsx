import { useEffect, useRef, useState, type DragEvent } from 'react'
import { ArrowDownToLine, ArrowRight, Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, FileVideo, Film, Focus, Image as ImageIcon, Info, KeyRound, LoaderCircle, Plus, ScanLine, Settings2, Sparkles, Upload, Video, Waves, X } from 'lucide-react'
import { api, downloadReport } from './api'
import { Field, Modal, Select, Toggle } from './components/ui'
import Results from './components/Results'
import { defaultProfile, defaultSettings, type Config, type Session, type Settings } from './types'

const focusOptions = [
  { id: 'general', label: 'Overall form' }, { id: 'strokes', label: 'Stroke' },
  { id: 'starts', label: 'Start' }, { id: 'turns', label: 'Turn' },
  { id: 'underwater', label: 'Underwater' }, { id: 'kicks', label: 'Kick' },
  { id: 'finishes', label: 'Finish' },
]
let bootstrap: Promise<[Config, Session]> | null = null
function loadApp() {
  if (!bootstrap) bootstrap = Promise.all([api<Config>('/config'), api<Session>('/session')]).catch(error => { bootstrap = null; throw error })
  return bootstrap
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState({ ...defaultProfile })
  const [settings, setSettings] = useState<Settings>({ ...defaultSettings })
  const [apiKey, setApiKey] = useState('')
  const [category, setCategory] = useState('general')
  const [loading, setLoading] = useState(true)
  const [operation, setOperation] = useState<'upload' | 'analyze' | 'chat' | 'reset' | ''>('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [modal, setModal] = useState<'settings' | 'guide' | 'reset' | null>(null)
  const [dragging, setDragging] = useState(false)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [videoUnavailable, setVideoUnavailable] = useState(false)
  const [selectedFrame, setSelectedFrame] = useState(0)
  const [pendingMessage, setPendingMessage] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const dragDepth = useRef(0)
  const busy = !!operation || loading
  const media = session?.media
  const connected = !!(apiKey.trim() || config?.api_key_configured)

  const initialize = () => {
    setLoading(true); setError('')
    void loadApp().then(([configuration, current]) => {
      setConfig(configuration); setSession(current); setProfile(current.profile); setCategory(current.category)
      setSettings(previous => ({ ...previous, model: configuration.models[0] || previous.model }))
    }).catch(error => setError(error.message)).finally(() => setLoading(false))
  }
  useEffect(initialize, [])
  useEffect(() => {
    if (!localFile) { setPreviewUrl(''); return }
    const url = URL.createObjectURL(localFile)
    setPreviewUrl(url); setVideoUnavailable(false)
    return () => URL.revokeObjectURL(url)
  }, [localFile])
  useEffect(() => { if (toast) { const timeout = setTimeout(() => setToast(''), 4500); return () => clearTimeout(timeout) } }, [toast])

  const setting = <K extends keyof Settings>(key: K, value: Settings[K]) => setSettings(previous => ({ ...previous, [key]: value }))
  const report = async () => {
    try { await downloadReport(); setToast('Your session report is ready.') } catch (error) { setError((error as Error).message) }
  }
  const upload = async (file: File) => {
    if (busy || !config) return
    setError('')
    const extension = '.' + file.name.split('.').pop()?.toLowerCase()
    if (![...config.image_extensions, ...config.video_extensions].includes(extension)) { setError('Choose a JPG, PNG, MP4, MOV, AVI, MKV, or M4V file.'); return }
    if (file.size > config.max_upload_mb * 1024 * 1024) { setError(`This file is too large. Choose a file under ${config.max_upload_mb} MB.`); return }
    if (!file.size) { setError('This file is empty. Try another image or video.'); return }
    setOperation('upload')
    const data = new FormData()
    data.append('file', file); data.append('max_frames', String(settings.max_frames)); data.append('smart', String(settings.smart_frames))
    try {
      const current = await api<Session>('/upload', { method: 'POST', body: data })
      setSession(current); setLocalFile(file); setSelectedFrame(0)
      setToast(current.media?.type === 'video' ? `${current.media.frame_count} frames ready for a closer look.` : 'Your image is ready for analysis.')
    } catch (error) { setError((error as Error).message) } finally { setOperation('') }
  }
  const analyze = async () => {
    if (busy || !media) return
    if (!connected) { setModal('settings'); return }
    setError(''); setOperation('analyze')
    if (window.innerWidth < 1000) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    try {
      const current = await api<Session>('/analyze', { method: 'POST', body: JSON.stringify({ profile, category, options: settings }) }, apiKey)
      setSession(current); setProfile(current.profile); setToast('Analysis ready.')
    } catch (error) { setError((error as Error).message) } finally { setOperation('') }
  }
  const chat = async (message: string) => {
    if (busy || !session?.analysis) return false
    if (!connected) { setModal('settings'); return false }
    setError(''); setOperation('chat'); setPendingMessage(message)
    try {
      const current = await api<Pick<Session, 'chat_messages' | 'profile'>>('/chat', { method: 'POST', body: JSON.stringify({ message, options: settings }) }, apiKey)
      setSession(previous => previous ? { ...previous, ...current } : previous)
      setProfile(previous => ({ ...previous, coach_notes: current.profile.coach_notes }))
      return true
    } catch (error) { setError((error as Error).message); return false } finally { setOperation(''); setPendingMessage('') }
  }
  const reset = async () => {
    if (busy) return
    setOperation('reset'); setError('')
    try {
      const current = await api<Session>('/session', { method: 'DELETE' })
      setSession(current); setLocalFile(null); setSelectedFrame(0)
      setProfile(previous => ({ ...previous, coach_notes: '' })); setModal(null); setToast('New session ready.')
    } catch (error) { setError((error as Error).message) } finally { setOperation('') }
  }
  const drop = (event: DragEvent) => {
    event.preventDefault(); setDragging(false); dragDepth.current = 0
    const files = event.dataTransfer.files
    if (files.length > 1) { setError('Choose one image or video at a time.'); return }
    if (files[0]) void upload(files[0])
  }

  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to analysis workspace</a>
    <aside className="sidebar">
      <a className="brand" href="#workspace" aria-label="Swimform workspace"><span className="brand-mark"><Waves size={26} strokeWidth={2.2} /></span><span>swimform<span className="brand-period">.</span></span></a>
      <nav className="main-nav" aria-label="Main navigation">
        <a className="nav-item active" href="#workspace" aria-current="page"><ScanLine size={19} /><span>Technique studio</span></a>
        <button className="nav-item" onClick={() => void report()} disabled={!session?.analysis || busy}><ArrowDownToLine size={19} /><span>Session report</span></button>
      </nav>
      <div className="sidebar-bottom"><button className="nav-item" onClick={() => setModal('guide')}><CircleHelp size={19} /><span>Filming guide</span></button><button className="nav-item" onClick={() => setModal('settings')} disabled={busy}><Settings2 size={19} /><span>Settings</span></button></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><a className="mobile-brand" href="#workspace" aria-label="Swimform workspace"><Waves size={22} /><strong>swimform.</strong></a><div className="topbar-actions"><button className="text-button tips-button" onClick={() => setModal('guide')}><Video size={16} />Filming guide</button><button className="icon-button mobile-settings" onClick={() => setModal('settings')} aria-label="Open settings" disabled={busy}><Settings2 size={20} /></button></div></header>
      <main id="workspace" className="workspace">
        <div className="page-heading"><div><h1>Technique studio</h1><p>Upload footage, choose a focus, and analyze your form.</p></div><button className="button secondary new-session" disabled={!media || busy} onClick={() => setModal('reset')}><Plus size={17} />New session</button></div>
        {error && <div className="error-banner" role="alert"><Info size={19} /><span>{error}</span>{!session && <button className="text-button" onClick={initialize}>Retry</button>}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={17} /></button></div>}
        <div className={`studio-grid ${session?.analysis ? 'with-chat' : ''}`}>
          <div className="input-column">
            <section className="panel footage-panel"><div className="panel-title"><h2>Your footage</h2></div>
              <input ref={fileInput} hidden tabIndex={-1} type="file" aria-label="Upload swimming footage" accept={config ? [...config.image_extensions, ...config.video_extensions].join(',') : '.jpg,.jpeg,.png,.mp4,.mov,.avi,.mkv,.m4v'} disabled={busy} onChange={event => { if (event.target.files?.[0]) void upload(event.target.files[0]); event.target.value = '' }} />
              <div className={`upload-area ${media ? 'has-media' : ''} ${dragging ? 'is-dragging' : ''}`} onDragEnter={event => { event.preventDefault(); if (!busy) { dragDepth.current++; setDragging(true) } }} onDragLeave={event => { event.preventDefault(); dragDepth.current--; if (dragDepth.current <= 0) setDragging(false) }} onDragOver={event => event.preventDefault()} onDrop={drop}>
                {operation === 'upload' ? <div className="upload-processing" role="status"><LoaderCircle size={34} className="spin" /><h3>Preparing footage…</h3></div> : media ? <>
                  <div className="media-preview">{media.type === 'video' && previewUrl && !videoUnavailable ? <video controls playsInline src={previewUrl} onError={() => setVideoUnavailable(true)} aria-label="Your uploaded swimming video" /> : <img src={media.frames[selectedFrame] || media.frames[0]} alt={media.type === 'video' ? `Extracted swimming frame ${selectedFrame + 1}` : 'Your uploaded swimming image'} />}
                    <span className="preview-badge">{media.type === 'video' ? 'Video' : 'Image'}</span>
                  </div>
                  <div className="media-info">{media.type === 'video' ? <FileVideo size={21} /> : <ImageIcon size={21} />}<span><strong title={media.name}>{media.name}</strong><small>{media.type === 'video' ? `${media.duration.toFixed(1)} sec · ${media.frame_count} frames selected` : 'Image prepared for analysis'}</small></span><button className="text-button" onClick={() => fileInput.current?.click()} disabled={busy}>Replace</button></div>
                  {videoUnavailable && <p className="preview-note">This video format cannot play in your browser. Your extracted frames are ready for analysis.</p>}
                </> : <div className="dropzone-content"><Film size={32} strokeWidth={1.5} /><h3>{dragging ? 'Drop your file here' : 'Upload swimming footage'}</h3><p>Drag and drop a photo or video, or choose a file.</p><button className="button upload-button" onClick={() => fileInput.current?.click()} disabled={busy}>{loading ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}{loading ? 'Getting ready…' : 'Choose file'}</button><span className="upload-limits">JPG, PNG, MP4, MOV, AVI, MKV, or M4V · {config?.max_upload_mb || 100} MB max</span></div>}
              </div>
              {media?.type === 'video' && <details className="frame-details"><summary><span><Film size={15} />{media.frame_count} extracted frames</span><ChevronRight size={15} /></summary><div className="frame-strip">{media.frames.map((url, index) => <button key={index} className={selectedFrame === index ? 'selected' : ''} aria-label={`Preview frame ${index + 1}`} aria-pressed={selectedFrame === index} onClick={() => { setSelectedFrame(index); setVideoUnavailable(true) }}><img src={url} alt={`Frame ${index + 1}`} /><span>{String(index + 1).padStart(2, '0')}</span></button>)}</div>{previewUrl && videoUnavailable && <button className="text-button" onClick={() => setVideoUnavailable(false)}>Back to video</button>}</details>}
              <div className="upload-tip"><Clock3 size={15} /><span>Keep clips under {config?.max_video_seconds || 30} seconds.</span><button onClick={() => setModal('guide')} className="text-button">Get the best angle<ArrowRight size={13} /></button></div>
              <div className="focus-section"><div className="section-label"><span><Focus size={16} />Analysis focus</span></div><div className="focus-options" role="group" aria-label="Analysis focus">{focusOptions.map(({ id, label }) => <button className={category === id ? 'selected' : ''} key={id} aria-pressed={category === id} disabled={busy} onClick={() => setCategory(id)}>{label}</button>)}</div></div>
            </section>
            <div className="analysis-action"><button className="button primary analyze-button" onClick={() => void analyze()} disabled={!media || busy}>{operation === 'analyze' ? <><LoaderCircle size={19} className="spin" />Analyzing…</> : <><Sparkles size={18} />{session?.analysis ? 'Analyze again' : 'Analyze technique'}<ArrowRight size={18} /></>}</button>{!connected && <div className="action-note"><KeyRound size={13} /><button className="text-button" onClick={() => setModal('settings')}>Add an API key to analyze</button></div>}</div>
          </div>
          <div ref={resultsRef} className="results-column"><Results session={session} analyzing={operation === 'analyze'} chatBusy={operation === 'chat'} busy={busy} onChat={chat} onDownload={() => void report()} pendingMessage={pendingMessage} /></div>
        </div>
      </main>
    </div>
    <Modal open={modal === 'settings'} onClose={() => setModal(null)} title="Settings" description="Configure API access and analysis.">
      <div className="modal-body"><section className="settings-section"><h3><KeyRound size={18} />API access</h3><Field label="OpenAI API key" hint={config?.api_key_configured ? 'A key is configured on your server. Enter a key only to override it for this tab.' : 'Your key is kept in memory in this tab, never saved to browser storage.'}><input type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={config?.api_key_configured ? 'Using your configured key' : 'sk-…'} /></Field>{connected && <div className="connection-message"><CheckCircle2 size={15} />{apiKey ? 'Key entered · checked when you analyze' : 'Server API key is configured'}</div>}</section>
        <section className="settings-section"><h3><Sparkles size={18} />Analysis</h3><Field label="AI model"><Select value={settings.model} onChange={value => setting('model', value)} options={config?.models.length ? config.models : [defaultSettings.model]} /></Field><div className="form-grid"><Field label="Image detail"><Select value={settings.image_detail} onChange={value => setting('image_detail', value as Settings['image_detail'])} options={['auto', 'low', 'high']} /></Field><Field label={`Chat creativity · ${settings.temperature.toFixed(1)}`}><input type="range" min="0" max="1.2" step="0.1" value={settings.temperature} onChange={event => setting('temperature', Number(event.target.value))} /></Field></div><Field label={`Video frames · ${settings.max_frames}`} hint="Applies to your next upload. More frames add detail and increase AI usage."><input type="range" min="5" max="20" step="1" value={settings.max_frames} onChange={event => setting('max_frames', Number(event.target.value))} /></Field><Toggle label="Smart frame selection" detail="Choose representative moments from your next video upload." checked={settings.smart_frames} onChange={value => setting('smart_frames', value)} /><Toggle label="Pose estimation" detail="Optional beta measurement hints. Availability depends on your Python setup." checked={settings.pose_enabled} onChange={value => setting('pose_enabled', value)} /><Toggle label="Recheck footage in chat" detail="Include your frames with follow-up questions. Uses more AI credits." checked={settings.include_media_on_followup} onChange={value => setting('include_media_on_followup', value)} /></section>
      </div><div className="modal-footer"><span>Preferences apply to this tab.</span><button className="button primary" onClick={() => setModal(null)}>Done<Check size={16} /></button></div>
    </Modal>
    <Modal open={modal === 'guide'} onClose={() => setModal(null)} title="Filming guide" description="Capture footage that is easy to analyze.">
      <div className="modal-body filming-guide">{[
        { icon: Video, title: 'Keep your whole body in frame', body: 'Film from the side and follow the swimmer steadily. Include the wall when you’re working on starts or turns.' },
        { icon: Clock3, title: 'Short, clear clips work best', body: 'Aim for a few complete stroke cycles in a clip under 30 seconds. Good light and a steady camera make the details easier to see.' },
        { icon: Waves, title: 'Show what happens below the surface', body: 'An underwater side view helps reveal body line and arm mechanics. An above-water view is useful for breathing, recovery, and timing.' },
      ].map(({ icon: Icon, title, body }) => <article key={title}><span className="guide-icon"><Icon size={23} /></span><div><h3>{title}</h3><p>{body}</p></div></article>)}</div><div className="modal-footer"><span>JPG, PNG, MP4, MOV, AVI, MKV, M4V</span><button className="button primary" onClick={() => setModal(null)}>Done<Check size={16} /></button></div>
    </Modal>
    <Modal open={modal === 'reset'} onClose={() => { if (!busy) setModal(null) }} title="Start a new session?" description="This clears your footage, analysis, and conversation.">
      <div className="modal-body reset-body"><p>{session?.analysis ? 'Download the current report first if you want to keep it.' : 'You can upload different footage after starting over.'}</p>{session?.analysis && <button className="button secondary" disabled={busy} onClick={() => void report()}><ArrowDownToLine size={16} />Download report</button>}</div><div className="modal-footer"><button className="text-button" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="button primary" disabled={busy} onClick={() => void reset()}>{operation === 'reset' ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}New session</button></div>
    </Modal>
    {toast && <div className="toast" role="status"><CheckCircle2 size={18} />{toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={15} /></button></div>}
  </div>
}
