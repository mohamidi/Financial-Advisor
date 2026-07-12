import { useEffect, useRef, useState } from 'react'
import './Chat.css'
import VerdictCard from '../components/VerdictCard'
import { Wave, ArrowRight, ArrowUp } from '../lib/icons'
import { CHAT_SUGGESTIONS } from '../lib/fields'
import * as api from '../lib/api'

// Real conversation: POST /chat with the stripped {role,text} history + the new message; the reply
// and its structured verdict come back and render as a message + verdict card. Tool results /
// verdicts are recomputed server-side each turn and never sent back up in history. (Real token-by-
// token SSE streaming is Increment 5; today the reply appears after the "thinking" state.)
export default function Chat() {
  const [messages, setMessages] = useState([]) // { role, text, verdict?, isError? }
  const [input, setInput] = useState('')
  const [status, setStatus] = useState('idle') // idle | thinking
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, status])

  async function ask(text) {
    if (status !== 'idle') return
    const history = messages.map(({ role, text: t }) => ({ role, text: t }))
    setMessages((m) => [...m, { role: 'user', text }])
    setStatus('thinking')
    try {
      const res = await api.sendChat(history, text)
      setMessages((m) => [...m, { role: 'assistant', text: res.reply, verdict: res.verdict || null }])
    } catch (e) {
      if (e.status === 401) return // logged out; App routes away
      const text2 = e.status === 429 ? e.detail : 'Sorry — something went wrong. Please try again.'
      setMessages((m) => [...m, { role: 'assistant', text: text2, isError: true }])
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
            ) : (
              <div className="asst rise" key={idx}>
                <p className={`asst-text serif${m.isError ? ' asst-error' : ''}`}>{m.text}</p>
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
