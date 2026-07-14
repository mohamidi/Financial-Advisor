import { useEffect, useRef, useState } from 'react'
import './Numbers.css'
import { money } from '../lib/format'

const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s)

// Ease-out count from the previously shown value to `target` — the hero figure settles like a
// balance updating. First mount counts up from 0; if the numbers later change (a chat turn updated
// the profile), it rolls from the old figure to the new one instead of hard-cutting. Skipped under
// prefers-reduced-motion (JS-driven, so the global CSS reduced-motion rule can't catch it).
function useCountUp(target, ms = 900) {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const [val, setVal] = useState(reduced ? target : 0)
  const fromRef = useRef(reduced ? target : 0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      fromRef.current = target
      setVal(target)
      return
    }
    const from = fromRef.current
    if (from === target) return
    let raf
    const t0 = performance.now()
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / ms)
      const v = from + (target - from) * (1 - Math.pow(1 - p, 3))
      fromRef.current = v
      setVal(v)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return val
}

// Scale against the full [min(0,…), max(0,…)] range rather than assuming the series is positive
// and rising — a negative surplus produces a falling line below the zero mark, not a garbage chart.
function projectionPaths(projection) {
  const pts = projection.map((p) => parseFloat(p.cumulative))
  const W = 320, H = 130, pad = 14
  const lo = Math.min(0, ...pts)
  const hi = Math.max(0, ...pts)
  const range = hi - lo || 1
  const xs = pts.map((_, i) => pad + i * ((W - 2 * pad) / (pts.length - 1)))
  const ys = pts.map((v) => H - pad - ((v - lo) / range) * (H - 2 * pad))
  const line = `M${xs[0].toFixed(1)} ${ys[0].toFixed(1)} ` +
    xs.slice(1).map((x, i) => `L${x.toFixed(1)} ${ys[i + 1].toFixed(1)}`).join(' ')
  const last = pts.length - 1
  const area = `${line} L${xs[last].toFixed(1)} ${H - pad} L${xs[0].toFixed(1)} ${H - pad} Z`
  return { line, area, endX: xs[last].toFixed(1), endY: ys[last].toFixed(1), end: pts[last] }
}

// `summary` is a cache owned by App and prefetched in the background right after login/onboarding
// (see App.jsx loadSummary), so in the common case this renders instantly with no loading flash.
// The effect below is only a fallback for the rare case this screen is reached before that prefetch
// resolves (or it errored) — it does not re-fetch on every visit.
export default function Numbers({ summary, loading, error, onRetry }) {
  useEffect(() => {
    if (!summary && !loading && !error) onRetry()
  }, [summary, loading, error, onRetry])

  const surplus = summary ? parseFloat(summary.monthly_surplus) : 0
  const heroVal = useCountUp(surplus)

  if (error) {
    return (
      <div className="numbers">
        <div className="hold num-state">
          Couldn’t load your numbers.{' '}
          <button className="num-retry" onClick={onRetry}>Try again</button>
        </div>
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
  const catMax = cats.length ? Math.max(...cats.map((c) => parseFloat(c.amount))) || 1 : 1
  const proj = projectionPaths(summary.projection)
  const saving = proj.end >= 0
  const p = summary.profile

  return (
    <div className="numbers">
      <div className="hold">
        <div className="num-title">
          <h1 className="serif">Your Numbers</h1>
          <span>Updated just now</span>
        </div>

        <div className="hero-card">
          <div className="hero-k"><i className={surplus >= 0 ? '' : 'neg'} />Monthly surplus</div>
          <div className="hero-big serif tnum">{money(heroVal)}</div>
          <div className="hero-sub tnum">
            Income <strong>{money(summary.monthly_income)}</strong> − avg spend{' '}
            <strong>{money(summary.avg_spend)}</strong>
          </div>
        </div>

        <div className="num-grid">
          <div className="num-card">
            <h2 className="num-ct">Spending by category</h2>
            <p className="num-cs">Where your money went this month</p>
            {cats.length === 0 ? (
              <p className="num-empty">No transactions yet — spending will show up here.</p>
            ) : (
              <div className="bars">
                {cats.map((c, i) => {
                  const amt = parseFloat(c.amount)
                  const top = amt === catMax
                  return (
                    <div className="brow" key={c.category} style={{ '--i': i }}>
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
            )}
          </div>

          <div className="num-card">
            <h2 className="num-ct">Cash-flow projection</h2>
            <p className="num-cs">If nothing changes over the next 6 months</p>
            <div className="proj-head">
              <span className="serif tnum">{money(Math.abs(proj.end))}</span>
              <span className={`proj-note${saving ? '' : ' short'}`}>
                {saving ? 'saved by month 6' : 'short by month 6'}
              </span>
            </div>
            <svg viewBox="0 0 320 130" className="proj-svg" preserveAspectRatio="none"
                 role="img"
                 aria-label={`Cash-flow projection ${saving ? 'rising to' : 'falling to a shortfall of'} ${money(Math.abs(proj.end))} over 6 months`}>
              <defs>
                <linearGradient id="proj-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={saving ? 'var(--accent)' : 'var(--no)'} stopOpacity="0.28" />
                  <stop offset="100%" stopColor={saving ? 'var(--accent)' : 'var(--no)'} stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={proj.area} fill="url(#proj-fill)" className="proj-area" />
              <path d={proj.line} fill="none" stroke={saving ? 'var(--accent)' : 'var(--no)'}
                    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                    pathLength="1" className="proj-line" />
              <circle cx={proj.endX} cy={proj.endY} r="5" fill={saving ? 'var(--accent)' : 'var(--no)'}
                      stroke="var(--surface)" strokeWidth="2.5" className="proj-dot" />
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
