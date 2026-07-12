import { useEffect, useRef, useState } from 'react'
import './Chat.css'
import VerdictCard from '../components/VerdictCard'
import { Wave, ArrowRight, ArrowUp } from '../lib/icons'
import { CHAT_SUGGESTIONS } from '../lib/fields'
import * as api from '../lib/api'

// Real conversation: POST /chat streams the reply as it's generated (SSE — see api.streamChat) —
// the assistant bubble grows as it's generated instead of appearing all at once after a wait. Tool
// results / verdicts are still recomputed server-side each turn and never sent back up in history;
// the verdict card only renders once the terminal "done" event carries the real computed numbers.
//
// The raw network deltas arrive in uneven bursts (Claude batches several tokens per SSE event, so a
// chunk might be 1 character or 70) — painting them straight to the DOM looks choppy. Instead every
// chunk lands in a buffer (revealBufRef) and a rAF loop drains it onto the screen at a steady pace,
// speeding up if a big burst piles up so the display never lags far behind. Same technique Claude's
// own UI uses to turn bursty network delivery into a smooth, constant-feeling typing motion.
const REVEAL_CHARS_PER_SEC = 65 // steady-state pace once caught up — a comfortable reading speed
const REVEAL_CATCH_UP_RATIO = 0.15 // fraction of the backlog drained per frame when it piles up

export default function Chat({ onProfileChanged }) {
  const [messages, setMessages] = useState([]) // { role, text, verdict?, isError?, streaming? }
  const [input, setInput] = useState('')
  const [status, setStatus] = useState('idle') // idle | thinking | streaming
  const listRef = useRef(null)
  const revealBufRef = useRef('') // text received but not yet painted
  const revealFrameRef = useRef(null)
  const revealLastTsRef = useRef(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, status])

  // Stops the reveal loop and drops anything still queued — used when a turn errors, so a half-typed
  // backlog from a failed stream never bleeds into the next message.
  function stopReveal() {
    if (revealFrameRef.current) cancelAnimationFrame(revealFrameRef.current)
    revealFrameRef.current = null
    revealLastTsRef.current = null
    revealBufRef.current = ''
  }

  function revealTick(ts) {
    const pending = revealBufRef.current
    if (!pending) {
      revealFrameRef.current = null
      revealLastTsRef.current = null
      return
    }
    const dt = revealLastTsRef.current ? (ts - revealLastTsRef.current) / 1000 : 1 / 60
    revealLastTsRef.current = ts
    const steady = Math.max(1, Math.round(REVEAL_CHARS_PER_SEC * dt))
    const catchUp = Math.round(pending.length * REVEAL_CATCH_UP_RATIO)
    const take = Math.min(pending.length, Math.max(steady, catchUp))
    revealBufRef.current = pending.slice(take)
    setMessages((m) => {
      const next = m.slice()
      const last = next[next.length - 1]
      next[next.length - 1] = { ...last, text: last.text + pending.slice(0, take) }
      return next
    })
    revealFrameRef.current = requestAnimationFrame(revealTick)
  }

  // Resolves once the reveal buffer has fully drained onto the screen — awaited before swapping in
  // the final message, so the visible text never jumps or truncates mid-animation.
  function waitForRevealDrain() {
    return new Promise((resolve) => {
      function check() {
        if (!revealBufRef.current && !revealFrameRef.current) resolve()
        else requestAnimationFrame(check)
      }
      check()
    })
  }

  async function ask(text) {
    if (status !== 'idle') return
    const history = messages.map(({ role, text: t }) => ({ role, text: t }))
    setMessages((m) => [...m, { role: 'user', text }])
    setStatus('thinking')
    startedRef.current = false // first text chunk hasn't arrived yet — still "thinking" (may be mid tool-call)
    try {
      const result = await api.streamChat(history, text, {
        onText: (chunk) => {
          if (!startedRef.current) {
            startedRef.current = true
            setStatus('streaming')
            setMessages((m) => [...m, { role: 'assistant', text: '', streaming: true }])
          }
          revealBufRef.current += chunk
          if (!revealFrameRef.current) revealFrameRef.current = requestAnimationFrame(revealTick)
        },
      })
      await waitForRevealDrain()
      // Swap the streaming bubble (or add a fresh one, if the reply was tool-only with no streamed
      // text) for the final message, now that the verdict card has real numbers to render.
      setMessages((m) => {
        const final = { role: 'assistant', text: result.reply, verdict: result.verdict || null }
        if (!startedRef.current) return [...m, final]
        const next = m.slice()
        next[next.length - 1] = final
        return next
      })
      // A turn can update the profile via save_profile (e.g. "add $2,000 to my debt"), which changes
      // the numbers dashboard — refresh that cache in the background so it never shows stale figures.
      // Cheap: one GET /summary, no extra Claude cost.
      onProfileChanged?.()
    } catch (e) {
      stopReveal()
      if (e.status === 401) return // logged out; App routes away
      const text2 = e.status === 429 ? e.detail : 'Sorry — something went wrong. Please try again.'
      setMessages((m) => {
        const base = startedRef.current ? m.slice(0, -1) : m // drop the partial streaming bubble, if any
        return [...base, { role: 'assistant', text: text2, isError: true }]
      })
    } finally {
      setStatus('idle')
    }
  }

  function send(e) {
    e.preventDefault()
    const t = input.trim()
    if (!t) return
    setInput('')
    ask(t)
  }

  const empty = messages.length === 0 && status === 'idle'

  return (
    <div className="chat">
      <div className="thread-scroll" ref={listRef} aria-live="polite">
        <div className="thread">
          {empty && (
            <div className="empty rise">
              <span className="empty-glyph"><Wave size={27} color="var(--accent)" /></span>
              <h2 className="serif">Ask me anything about your money.</h2>
              <p>
                I know your income, spending and debt. I’ll tell you straight whether something’s a{' '}
                <strong>yes</strong>, <strong>risky</strong>, or a <strong>no</strong> — and show the math.
              </p>
              <div className="sugg">
                {CHAT_SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => ask(s)}>
                    <ArrowRight size={15} />{s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, idx) =>
            m.role === 'user' ? (
              <div className="row-end rise" key={idx}>
                <div className="bubble-user">{m.text}</div>
              </div>
            ) : m.streaming ? (
              <div className="stream rise" key={idx}>
                <div className="bubble-assistant">
                  <p className="serif">{m.text}<span className="caret" /></p>
                </div>
              </div>
            ) : (
              <div className="asst rise" key={idx}>
                <div className={`bubble-assistant${m.isError ? ' asst-error' : ''}`}>
                  <p className="serif">{m.text}</p>
                </div>
                {m.verdict && <VerdictCard verdict={m.verdict} />}
              </div>
            )
          )}

          {status === 'thinking' && (
            <div className="thinking rise">
              <span className="dots"><i /><i /><i /></span>
              <span>Crunching your numbers…</span>
            </div>
          )}
        </div>
      </div>

      <div className="composer">
        <form onSubmit={send}>
          <input
            placeholder="Ask about a purchase, bill, or goal…" value={input}
            onChange={(e) => setInput(e.target.value)} aria-label="Message"
          />
          <button type="submit" className="send" aria-label="Send" disabled={!input.trim() || status !== 'idle'}>
            <ArrowUp size={20} />
          </button>
        </form>
      </div>
    </div>
  )
}
