import { useEffect, useState } from 'react'
import './Onboarding.css'
import * as api from '../lib/api'
import { mergeQuestions } from '../lib/fields'
import MoneyInput from '../components/MoneyInput'
import { Check, AlertCircle, Wave } from '../lib/icons'

// Questions/prompts/order + validation are server-owned (GET /onboarding/questions, POST
// /onboarding); the client adds widget metadata (mergeQuestions) and mirrors the validation for
// instant feedback. A server 422 maps back to the offending field's inline error.
export default function Onboarding({ onFinished }) {
  const [phase, setPhase] = useState('welcome') // welcome (fades out) → questions
  const [leaving, setLeaving] = useState(false)
  const [questions, setQuestions] = useState(null)
  const [loadError, setLoadError] = useState(false)
  const [i, setI] = useState(0)
  const [answers, setAnswers] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api.getQuestions()
      .then((qs) => setQuestions(mergeQuestions(qs)))
      .catch((e) => { if (e.status !== 401) setLoadError(true) })
  }, [])

  function begin() {
    setLeaving(true)
    setTimeout(() => setPhase('questions'), 340)
  }

  if (phase === 'welcome') {
    return (
      <div className="ob ob-welcome-wrap">
        <div className={`ob-welcome${leaving ? ' leaving' : ''}`}>
          <span className="ob-welcome-badge"><Wave size={26} color="#fff" /></span>
          <h1 className="serif ob-welcome-h1">Welcome to Floated.</h1>
          <p className="ob-welcome-p">
            A few quick questions about your money — income, spending, debt — so every answer I give
            you is grounded in your real numbers, not guesses. Takes about a minute.
          </p>
          <button className="btn btn-primary ob-welcome-btn" onClick={begin}>Get started</button>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="ob ob-welcome-wrap">
        <div className="ob-welcome">
          <p className="ob-welcome-p">Couldn’t load your setup questions. Please refresh and try again.</p>
        </div>
      </div>
    )
  }

  if (!questions) {
    return <div className="ob ob-welcome-wrap"><p className="ob-loading">Loading…</p></div>
  }

  const q = questions[i]
  const value = answers[q.field] ?? ''
  const last = i === questions.length - 1
  const set = (v) => { setAnswers((a) => ({ ...a, [q.field]: v })); setError('') }
  const setDigits = (raw) => set(raw.replace(/[^\d]/g, ''))
  const back = () => { setI((x) => Math.max(0, x - 1)); setError('') }

  function validate() {
    if (!q.optional && String(value).trim() === '') return 'This can’t be blank.'
    if (q.field === 'age') {
      const raw = String(value).trim()
      if (!/^\d+$/.test(raw)) return 'Please enter your age as a whole number.'
      const age = Number(raw)
      if (age < 18) return 'You must be 18 or older to use Floated.'
      if (age > 120) return 'Please enter a valid age.'
    }
    return ''
  }

  async function submit() {
    setSubmitting(true)
    try {
      const profile = await api.submitOnboarding(answers)
      onFinished(profile)
    } catch (e) {
      setSubmitting(false)
      if (e.status === 422) {
        const idx = questions.findIndex((qq) => e.errors[qq.field])
        if (idx >= 0) { setI(idx); setError(e.errors[questions[idx].field]) }
        else setError('Please double-check your answers.')
      } else if (e.status !== 401) {
        setError('Something went wrong saving your profile. Please try again.')
      }
    }
  }

  function next() {
    const msg = validate()
    if (msg) return setError(msg)
    if (last) return submit()
    setI((x) => x + 1)
    setError('')
  }

  return (
    <div className="ob">
      <div className="hold hold-md">
        <div className="ob-top">
          <span className="ob-count tnum">Question {i + 1} of {questions.length}</span>
          <span className="ob-time">Takes about a minute</span>
        </div>
        <div className="ob-track"><i style={{ width: `${((i + 1) / questions.length) * 100}%` }} /></div>

        <div className="ob-body rise" key={i}>
          <h2 className="serif ob-q">{q.prompt}</h2>

          {q.type === 'enum' && (
            <div className="ob-options">
              {q.options.map((o) => {
                const sel = value === o.v
                return (
                  <button type="button" key={o.v} className={`ob-opt${sel ? ' sel' : ''}`} onClick={() => set(o.v)}>
                    <span className="ob-dot">{sel && <Check size={12} />}</span>
                    <span className="ob-ot">
                      <span className="ob-ol">{o.l}</span>
                      {o.sub && <span className="ob-os">{o.sub}</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {q.type === 'money' && (
            <div className="ob-money">
              <span className="ob-cur serif">$</span>
              <MoneyInput className="ob-money-in serif tnum" placeholder={q.placeholder} value={value} onChange={set} />
            </div>
          )}

          {q.type === 'number' && (
            <input
              inputMode="numeric" className="ob-num serif tnum" placeholder={q.placeholder}
              value={value} onChange={(e) => setDigits(e.target.value)}
            />
          )}

          {q.type === 'text' && (
            <textarea rows={4} className="ob-text" placeholder={q.placeholder} value={value} onChange={(e) => set(e.target.value)} />
          )}

          {error && (
            <div className="ob-err" role="alert"><AlertCircle size={16} />{error}</div>
          )}
        </div>

        <div className="ob-nav">
          {i > 0 && <button className="btn btn-secondary ob-back" onClick={back}>Back</button>}
          <button className="btn btn-primary ob-next" onClick={next} disabled={submitting}>
            {submitting ? (<><span className="spinner" />Setting up…</>) : last ? 'Finish' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}
