// Money arrives from the API as exact 2-dp strings (e.g. "8000.00"). Display rounds to whole
// dollars unless `cents` is requested — matching the Floated mockups ($8,000, $3,423).
// Live-format a money field AS the user types: group the integer part with commas, keep at most one
// decimal point and 2 places. Returns a display string ("6,800", "1,250.50"); the server strips
// commas on submit, so it stays a valid amount.
export function formatMoneyInput(raw) {
  let s = String(raw).replace(/[^\d.]/g, '')
  const dot = s.indexOf('.')
  if (dot !== -1) {
    // keep only the first dot
    s = s.slice(0, dot + 1) + s.slice(dot + 1).replace(/\./g, '')
  }
  let [intPart, decPart] = s.split('.')
  intPart = intPart.replace(/^0+(?=\d)/, '') // drop leading zeros
  const grouped = intPart ? Number(intPart).toLocaleString('en-US') : ''
  if (decPart !== undefined) return `${grouped || '0'}.${decPart.slice(0, 2)}`
  return grouped
}

export function money(value, { cents = false, sign = false } = {}) {
  const n = typeof value === 'number' ? value : parseFloat(value)
  if (Number.isNaN(n)) return String(value)
  const abs = Math.abs(n)
  const body = abs.toLocaleString('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })
  const s = sign && n > 0 ? '+' : n < 0 ? '−' : ''
  return `${s}$${body}`
}
