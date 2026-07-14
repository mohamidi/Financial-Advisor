import './VerdictCard.css'
import { VerdictIcon, Flag } from '../lib/icons'
import { money } from '../lib/format'

// The reasoning comes from the deterministic verdict engine, so its figures follow known shapes:
// "$8000.00", "1.4x", "2.3 months". Bold them so the numbers that drove the verdict pop out of the
// sentence (the design handoff's inline-figure treatment). Everything else renders as plain text —
// this only ever splits a server-built string, no user input.
const FIGURE_RE = /(\$[\d,]+(?:\.\d+)?|\b\d+(?:\.\d+)?x\b|\b\d+(?:\.\d+)?\s+months?\b)/g

function BoldFigures({ text }) {
  return text.split(FIGURE_RE).map((part, i) =>
    i % 2 === 1 ? <strong key={i} className="tnum">{part}</strong> : part
  )
}

// Consumes the /chat `verdict` block. The verdict is NEVER conveyed by color alone — the pill
// always carries the word + an icon (accessibility non-negotiable from the design spec).
export default function VerdictCard({ verdict }) {
  const v = verdict.verdict // 'yes' | 'risky' | 'no'
  const stats = [
    { k: 'Cost', v: money(verdict.cost) },
    { k: 'Surplus / mo', v: money(verdict.monthly_surplus) },
  ]
  if (verdict.months_to_absorb) stats.push({ k: 'Months to absorb', v: `≈${verdict.months_to_absorb}` })
  const flags = verdict.risk_flags || []

  return (
    <div className="vcard">
      <span className={`vpill v-${v}`}>
        <VerdictIcon verdict={v} size={15} />
        {v.toUpperCase()}
      </span>
      <h3 className="vhead serif">{verdict.summary}</h3>
      <p className="vreason"><BoldFigures text={verdict.reasoning} /></p>

      <div className="vstats tnum" style={{ gridTemplateColumns: `repeat(${stats.length}, 1fr)` }}>
        {stats.map((s) => (
          <div className="vcell" key={s.k}>
            <div className="vk">{s.k}</div>
            <div className="vv serif">{s.v}</div>
          </div>
        ))}
      </div>

      {flags.length > 0 && (
        <div className="vflags">
          {flags.map((f, i) => (
            <div className="vflag" key={i}>
              <Flag size={14} />
              <span>{f}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
