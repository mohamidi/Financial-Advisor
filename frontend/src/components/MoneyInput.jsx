import { useRef } from 'react'
import { formatMoneyInput } from '../lib/format'

// A money input that groups thousands live. Reformatting rewrites the field value on each keystroke,
// which makes the browser jump the caret to the end (and Firefox select the whole field — the
// "highlight" bug). So after formatting we restore the caret to just after the same digit the user
// was on, and collapse any selection.
export default function MoneyInput({ value, onChange, placeholder, className }) {
  const ref = useRef(null)

  function handle(e) {
    const el = e.target
    const digitsBeforeCaret = (el.value.slice(0, el.selectionStart).match(/[\d.]/g) || []).length
    const formatted = formatMoneyInput(el.value)
    onChange(formatted)
    requestAnimationFrame(() => {
      const node = ref.current
      if (!node) return
      let pos = 0
      let seen = 0
      while (pos < formatted.length && seen < digitsBeforeCaret) {
        if (/[\d.]/.test(formatted[pos])) seen += 1
        pos += 1
      }
      node.setSelectionRange(pos, pos)
    })
  }

  return (
    <input
      ref={ref}
      inputMode="numeric"
      className={className}
      placeholder={placeholder}
      value={value}
      onChange={handle}
    />
  )
}
