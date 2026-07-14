// Minimal, safe inline markdown for the advisor's chat replies: only **bold** is recognized. The
// model reliably emphasizes verdicts/figures this way ("**yes, you can afford it**"), so without
// this the literal asterisks leak into the bubble as visible text. No HTML is ever injected here —
// this only decides which spans of the model's own plain-text reply render as <strong>, so there's
// no new XSS surface beyond what plain-text rendering already had.
export default function InlineMarkdown({ text }) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  )
}
