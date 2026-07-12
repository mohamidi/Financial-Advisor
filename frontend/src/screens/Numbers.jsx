import { useEffect, useState } from 'react'
import './Numbers.css'
import { money } from '../lib/format'
import * as api from '../lib/api'

const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s)

function projectionPaths(projection) {
  const pts = projection.map((p) => parseFloat(p.cumulative))
  const W = 320, H = 130, pad = 14
  const pmax = pts[pts.length - 1] || 1
  const xs = pts.map((_, i) => pad + i * ((W - 2 * pad) / (pts.length - 1)))
  const ys = pts.map((v) => H - pad - (v / pmax) * (H - 2 * pad))
  const line = `M${xs[0].toFixed(1)} ${ys[0].toFixed(1)} ` +
    xs.slice(1).map((x, i) => `L${x.toFixed(1)} ${ys[i + 1].toFixed(1)}`).join(' ')
  const last = pts.length - 1
  const area = `${line} L${xs[last].toFixed(1)} ${H - pad} L${xs[0].toFixed(1)} ${H - pad} Z`
  return { line, area, endX: xs[last].toFixed(1), endY: ys[last].toFixed(1), end: pts[last] }
}

export default function Numbers() {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.getSummary()
      .then(setSummary)
      .catch((e) => { if (e.status !== 401) setError(true) })
  }, [])

  if (error) {
    return (
      <div className="numbers">
        <div className="hold num-state">Couldn’t load your numbers. Please try again.</div>
      </div>
    )
  }
  if (!summary) {
    return (
      <div className="numbers">
        <div className="hold num-state">Loading your numbers…</div>
      </div>
    )
  }

  const cats = summary.spending_by_category
  const catMax = Math.max(...cats.map((c) => parseFloat(c.amount)))
  const proj = projectionPaths(summary.projection)
  const p = summary.profile

  return (
    <div className="numbers">
      <div className="hold">
        <div className="num-title">
          <h1 className="serif">Your Numbers</h1>
          <span>Updated just now</span>
        </div>

        <div className="hero-card">
          <div className="hero-k"><i />Monthly surplus</div>
          <div className="hero-big serif tnum">{money(summary.monthly_surplus)}</div>
          <div className="hero-sub tnum">
            Income <strong>{money(summary.monthly_income)}</strong> − avg spend{' '}
            <strong>{money(summary.avg_spend)}</strong>
          </div>
        </div>

        <div className="num-grid">
          <div className="num-card">
            <h2 className="num-ct">Spending by category</h2>
            <p className="num-cs">Where your money went this month</p>
            <div className="bars">
              {cats.map((c) => {
                const amt = parseFloat(c.amount)
                const top = amt === catMax
                return (
                  <div className="brow" key={c.category}>
                    <div className="brow-head">
                      <span className={`brow-lbl${top ? ' top' : ''}`}>{c.category}</span>
                      <span className={`brow-amt tnum${top ? ' top' : ''}`}>{money(c.amount)}</span>
                    </div>
                    <div className="brow-track">
                      <i className={top ? 'top' : ''} style={{ width: `${(amt / catMax) * 100}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="num-card">
            <h2 className="num-ct">Cash-flow projection</h2>
            <p className="num-cs">If nothing changes over the next 6 months</p>
            <div className="proj-head">
              <span className="serif tnum">{money(proj.end)}</span>
              <span className="proj-note">saved by month 6</span>
            </div>
            <svg viewBox="0 0 320 130" className="proj-svg" preserveAspectRatio="none"
                 role="img" aria-label={`Cash-flow projection rising to ${money(proj.end)} over 6 months`}>
              <defs>
                <linearGradient id="proj-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={proj.area} fill="url(#proj-fill)" />
              <path d={proj.line} fill="none" stroke="var(--accent)" strokeWidth="2.5"
                    strokeLinecap="round" strokeLinejoin="round" />
              <circle cx={proj.endX} cy={proj.endY} r="5" fill="var(--accent)"
                      stroke="var(--surface)" strokeWidth="2.5" />
            </svg>
            <div className="proj-axis tnum"><span>Now</span><span>+3 mo</span><span>+6 mo</span></div>
          </div>
        </div>

        <h2 className="num-section">Profile at a glance</h2>
        <div className="chips">
          <div className="chip"><div className="chip-k">Income</div><div className="chip-v serif tnum">{money(p.monthly_income)}<span>/mo</span></div></div>
          <div className="chip"><div className="chip-k">Total debt</div><div className="chip-v serif tnum">{money(p.existing_debt)}</div></div>
          <div className="chip"><div className="chip-k">Risk</div><div className="chip-v serif">{cap(p.risk_tolerance)}</div></div>
          <div className="chip"><div className="chip-k">Dependents</div><div className="chip-v serif tnum">{p.dependents}</div></div>
        </div>
      </div>
    </div>
  )
}
