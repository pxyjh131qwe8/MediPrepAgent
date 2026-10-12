import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Check,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  HeartPulse,
  Menu,
  MessageCircleQuestion,
  Plus,
  Send,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from 'lucide-react'
import { checkServer, consultHealth } from './api'
import type { ConsultationTurn, ConsultRequest, ConsultResponse, RiskLevel } from './types'
import visitPrepImage from './assets/visit-prep.webp'

interface Session {
  id: string
  title: string
  turns: ConsultationTurn[]
}

interface FormState {
  symptoms: string
  age: string
  gender: string
  duration: string
  medicalHistory: string
  medicationHistory: string
  allergyHistory: string
  goal: string
}

const emptyForm: FormState = {
  symptoms: '',
  age: '',
  gender: '',
  duration: '',
  medicalHistory: '',
  medicationHistory: '',
  allergyHistory: '',
  goal: '',
}

const createId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

const createSession = (): Session => ({ id: createId(), title: '新的就诊准备', turns: [] })

const examples = [
  '头痛三天，太阳穴一跳一跳地疼，没有恶心和肢体无力',
  '咳嗽一周，晚上更明显，偶尔有白痰，没有呼吸困难',
  '最近两周总是睡不着，白天很疲惫，想知道该挂什么科',
]

const loadingSteps = ['安全分诊正在识别危险信号', '证据专员正在检索医学资料', '就诊规划专员正在整理建议', '安全复核正在核对边界', '正在把话说得更自然一些']

const riskCopy: Record<RiskLevel, { label: string; short: string }> = {
  LOW: { label: '暂未发现明确急症信号', short: '常规关注' },
  MEDIUM: { label: '建议近期安排线下就诊', short: '尽快就诊' },
  HIGH: { label: '存在需要立即排查的信号', short: '立即处理' },
}

function App() {
  const firstSession = useMemo(createSession, [])
  const [sessions, setSessions] = useState<Session[]>([firstSession])
  const [activeId, setActiveId] = useState(firstSession.id)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [pendingText, setPendingText] = useState('')
  const [error, setError] = useState('')
  const [serverOnline, setServerOnline] = useState<boolean | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const activeSession = sessions.find((session) => session.id === activeId) ?? sessions[0]

  useEffect(() => {
    checkServer().then(setServerOnline)
  }, [])

  useEffect(() => {
    if (!loading) return
    setLoadingStep(0)
    const timer = window.setInterval(
      () => setLoadingStep((step) => Math.min(step + 1, loadingSteps.length - 1)),
      1100,
    )
    return () => window.clearInterval(timer)
  }, [loading])

  const updateField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const selectSession = (id: string) => {
    setActiveId(id)
    setForm(emptyForm)
    setError('')
    setSidebarOpen(false)
  }

  const startNewSession = () => {
    const session = createSession()
    setSessions((current) => [session, ...current])
    setActiveId(session.id)
    setForm(emptyForm)
    setError('')
    setSidebarOpen(false)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const symptoms = form.symptoms.trim()
    if (symptoms.length < 2 || loading) return

    const request: ConsultRequest = {
      symptoms,
      age: form.age ? Number(form.age) : undefined,
      gender: form.gender || undefined,
      duration: form.duration.trim() || undefined,
      medical_history: form.medicalHistory.trim() || undefined,
      medication_history: form.medicationHistory.trim() || undefined,
      allergy_history: form.allergyHistory.trim() || undefined,
      goal: form.goal.trim() || '想知道紧急程度、适合的科室，以及就诊前需要准备什么',
      thread_id: activeSession.id,
      use_saved_context: activeSession.turns.length > 0,
    }

    setLoading(true)
    setError('')
    setPendingText(symptoms)
    try {
      const response = await consultHealth(request)
      const turn: ConsultationTurn = { id: createId(), request, response }
      setSessions((current) =>
        current.map((session) =>
          session.id === activeSession.id
            ? {
                ...session,
                title: session.turns.length ? session.title : symptoms.slice(0, 18),
                turns: [...session.turns, turn],
              }
            : session,
        ),
      )
      setForm((current) => ({ ...emptyForm, age: current.age, gender: current.gender }))
      setServerOnline(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '这次没有顺利完成，请稍后再试。')
      setServerOnline(false)
    } finally {
      setLoading(false)
      setPendingText('')
    }
  }

  return (
    <div className="app-shell">
      <button className="mobile-menu icon-button" onClick={() => setSidebarOpen(true)} aria-label="打开会话列表">
        <Menu size={20} />
      </button>

      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <span className="brand-mark"><HeartPulse size={20} /></span>
          <div>
            <strong>MediPrep</strong>
            <span>就诊准备助手</span>
          </div>
          <button className="sidebar-close icon-button" onClick={() => setSidebarOpen(false)} aria-label="关闭会话列表">
            <X size={18} />
          </button>
        </div>

        <button className="new-session" onClick={startNewSession}>
          <Plus size={17} />
          新建咨询
        </button>

        <div className="sidebar-section-label">本次打开的咨询</div>
        <nav className="session-list" aria-label="咨询列表">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-item ${session.id === activeSession.id ? 'active' : ''}`}
              onClick={() => selectSession(session.id)}
            >
              <MessageCircleQuestion size={16} />
              <span>{session.title}</span>
              {session.turns.length > 0 && <small>{session.turns.length}</small>}
            </button>
          ))}
        </nav>

        <div className="sidebar-trust">
          <ShieldCheck size={18} />
          <div>
            <strong>只做就诊准备</strong>
            <span>不诊断，不开药，不替代医生</span>
          </div>
        </div>
        <p className="session-note">本页会话只保留在当前标签页中。</p>
      </aside>

      {sidebarOpen && <button className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-label="关闭侧栏" />}

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="topbar-kicker">当前咨询</span>
            <h1>{activeSession.title}</h1>
          </div>
          <div className={`server-state ${serverOnline === false ? 'offline' : ''}`}>
            <span />
            {serverOnline === null ? '正在连接' : serverOnline ? '协作组已就绪' : '后端未连接'}
          </div>
        </header>

        <div className="conversation">
          {activeSession.turns.length === 0 && !loading ? (
            <Welcome onChoose={(value) => updateField('symptoms', value)} />
          ) : (
            <div className="turn-list">
              {activeSession.turns.map((turn) => (
                <ConsultationResult key={turn.id} turn={turn} onFollowUp={(value) => updateField('symptoms', value)} />
              ))}
              {loading && <PendingTurn text={pendingText} step={loadingStep} />}
            </div>
          )}
        </div>

        <ConsultForm form={form} loading={loading} error={error} onChange={updateField} onSubmit={submit} />
      </main>
    </div>
  )
}

function Welcome({ onChoose }: { onChoose: (value: string) => void }) {
  return (
    <section className="welcome">
      <div className="welcome-copy">
        <span className="eyebrow"><Users size={16} /> 多 Agent 协作</span>
        <h2>先把情况说清楚，<br />我们一起准备好这次就诊。</h2>
        <p>你可以像平时说话一样描述不舒服。系统会先看紧急程度，再核对医学资料，最后给出科室和准备清单。</p>
        <div className="example-list">
          {examples.map((example) => (
            <button key={example} onClick={() => onChoose(example)}>{example}</button>
          ))}
        </div>
      </div>
      <figure className="welcome-visual">
        <img src={visitPrepImage} alt="医生与就诊者一起整理就诊信息的插画" />
        <figcaption><ClipboardCheck size={16} /> 把症状、时间和疑问先记下来，见医生时会更从容。</figcaption>
      </figure>
    </section>
  )
}

function ConsultForm({
  form,
  loading,
  error,
  onChange,
  onSubmit,
}: {
  form: FormState
  loading: boolean
  error: string
  onChange: (field: keyof FormState, value: string) => void
  onSubmit: (event: FormEvent) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="composer-wrap">
      {error && <div className="form-error" role="alert"><AlertTriangle size={17} />{error}</div>}
      <form className="composer" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="symptoms">描述你的不舒服</label>
        <textarea
          id="symptoms"
          value={form.symptoms}
          onChange={(event) => onChange('symptoms', event.target.value)}
          placeholder="比如：头痛三天，太阳穴跳着疼，没有恶心，晚上睡得不太好……"
          rows={3}
          maxLength={2000}
        />
        <div className="composer-actions">
          <button type="button" className="details-toggle" onClick={() => setExpanded((value) => !value)}>
            <ChevronDown size={16} className={expanded ? 'rotated' : ''} />
            {expanded ? '收起补充信息' : '补充年龄、病史等信息'}
          </button>
          <span className="char-count">{form.symptoms.length}/2000</span>
          <button className="send-button" type="submit" disabled={loading || form.symptoms.trim().length < 2}>
            <Send size={17} />
            {loading ? '正在整理' : '开始分析'}
          </button>
        </div>

        {expanded && (
          <div className="detail-fields">
            <label>年龄<input type="number" min="0" max="120" value={form.age} onChange={(e) => onChange('age', e.target.value)} placeholder="选填" /></label>
            <label>性别<select value={form.gender} onChange={(e) => onChange('gender', e.target.value)}><option value="">选填</option><option>女</option><option>男</option><option>其他</option><option>不便透露</option></select></label>
            <label>持续时间<input value={form.duration} onChange={(e) => onChange('duration', e.target.value)} placeholder="如 3 天" /></label>
            <label className="wide">这次最想解决<input value={form.goal} onChange={(e) => onChange('goal', e.target.value)} placeholder="如：想知道该挂什么科" /></label>
            <label className="wide">既往病史<input value={form.medicalHistory} onChange={(e) => onChange('medicalHistory', e.target.value)} placeholder="没有可不填" /></label>
            <label className="wide">正在使用的药物<input value={form.medicationHistory} onChange={(e) => onChange('medicationHistory', e.target.value)} placeholder="药名即可，不清楚可不填" /></label>
            <label className="wide">过敏史<input value={form.allergyHistory} onChange={(e) => onChange('allergyHistory', e.target.value)} placeholder="没有可不填" /></label>
          </div>
        )}
      </form>
      <p className="composer-disclaimer">内容仅用于健康科普和就诊准备。紧急或明显加重时，请直接联系 120 或前往急诊。</p>
    </div>
  )
}

function PendingTurn({ text, step }: { text: string; step: number }) {
  return (
    <div className="turn-block">
      <div className="user-message"><span>你的描述</span><p>{text}</p></div>
      <div className="working-state" aria-live="polite">
        <div className="working-icon"><Activity size={21} /></div>
        <div><strong>{loadingSteps[step]}</strong><span>{step + 1} / {loadingSteps.length}</span></div>
        <div className="progress-track"><span style={{ width: `${((step + 1) / loadingSteps.length) * 100}%` }} /></div>
      </div>
    </div>
  )
}

function ConsultationResult({ turn, onFollowUp }: { turn: ConsultationTurn; onFollowUp: (value: string) => void }) {
  const result = turn.response
  const risk = result.risk_result
  return (
    <article className="turn-block">
      <div className="user-message"><span>你的描述</span><p>{turn.request.symptoms}</p></div>
      <div className="result-header">
        <span className="result-avatar"><HeartPulse size={20} /></span>
        <div><strong>MediPrep 协作结果</strong><span>{result.agent_trace.length} 位专员已完成整理与复核</span></div>
      </div>

      <section className={`risk-banner risk-${risk.risk_level.toLowerCase()}`}>
        <div className="risk-icon">{risk.risk_level === 'HIGH' ? <AlertTriangle /> : <ShieldCheck />}</div>
        <div>
          <span>{riskCopy[risk.risk_level].short}</span>
          <h2>{riskCopy[risk.risk_level].label}</h2>
          <p>{risk.action}</p>
        </div>
      </section>

      <p className="summary-text">{result.summary}</p>

      <div className="result-grid">
        <section className="result-panel department-panel">
          <div className="panel-title"><Stethoscope size={19} /><span>建议首诊科室</span></div>
          <strong className="department-name">{result.department_result.primary_department}</strong>
          <p>{result.department_result.reason}</p>
          {result.department_result.alternative_departments.length > 0 && (
            <div className="alternatives">备选：{result.department_result.alternative_departments.join('、')}</div>
          )}
        </section>

        <section className="result-panel">
          <div className="panel-title"><Clock3 size={19} /><span>需要留意</span></div>
          {risk.warnings.length ? <BulletList items={risk.warnings} tone="warning" /> : <p className="quiet-copy">目前没有识别到明确的危险表现，仍请留意症状变化。</p>}
          {risk.negated_signals.length > 0 && <p className="negated-note"><Check size={15} />已识别你明确否认：{risk.negated_signals.join('、')}</p>}
        </section>

        <section className="result-panel span-two">
          <div className="panel-title"><ClipboardCheck size={19} /><span>就诊前准备</span></div>
          <Checklist items={result.pre_visit_checklist} />
        </section>

        <section className="result-panel">
          <div className="panel-title"><BookOpen size={19} /><span>可能相关的因素</span></div>
          <BulletList items={result.possible_causes} />
        </section>

        <section className="result-panel">
          <div className="panel-title"><HeartPulse size={19} /><span>现在可以做的事</span></div>
          <BulletList items={result.lifestyle_advice} />
        </section>
      </div>

      {result.follow_up_questions.length > 0 && (
        <section className="follow-up-section">
          <div className="panel-title"><MessageCircleQuestion size={19} /><span>再补充这些，会更有帮助</span></div>
          <div className="follow-up-list">
            {result.follow_up_questions.map((question) => <button key={question} onClick={() => onFollowUp(question)}>{question}</button>)}
          </div>
        </section>
      )}

      <EvidenceAndTrace result={result} />
      <p className="medical-disclaimer"><ShieldCheck size={16} />{result.disclaimer}</p>
    </article>
  )
}

function EvidenceAndTrace({ result }: { result: ConsultResponse }) {
  return (
    <div className="audit-row">
      <details>
        <summary><BookOpen size={17} />资料依据 <span>{result.evidence.length}</span></summary>
        <div className="detail-content">
          {result.evidence.length ? result.evidence.map((item) => (
            <div className="evidence-item" key={`${item.source}-${item.excerpt.slice(0, 20)}`}>
              <div><strong>{item.title}</strong><span>{item.source}</span></div>
              <p>{item.excerpt}</p>
            </div>
          )) : <p className="quiet-copy">这次没有检索到直接相关资料，系统已采用保守建议。</p>}
          {result.quality.limitations.map((item) => <p className="limitation" key={item}>{item}</p>)}
        </div>
      </details>
      <details>
        <summary><Users size={17} />协作过程 <span>{result.agent_trace.length}</span></summary>
        <div className="detail-content trace-list">
          {result.agent_trace.map((step) => (
            <div className="trace-item" key={step.agent}>
              <span className={`trace-dot ${step.status}`}><Check size={12} /></span>
              <div><strong>{step.role}</strong><p>{step.summary}</p></div>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

function BulletList({ items, tone }: { items: string[]; tone?: 'warning' }) {
  return <ul className={`bullet-list ${tone ?? ''}`}>{items.map((item) => <li key={item}>{item}</li>)}</ul>
}

function Checklist({ items }: { items: string[] }) {
  return <ul className="checklist">{items.map((item) => <li key={item}><span><Check size={14} /></span>{item}</li>)}</ul>
}

export default App
