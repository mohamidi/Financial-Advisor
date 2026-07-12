import { useState } from 'react'
import './Login.css'
import { AlertCircle } from '../lib/icons'
import * as api from '../lib/api'

// Real Supabase auth: on success App fetches the profile and routes (onboarding vs chat).
export default function Login({ onAuthenticated }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null) // 'creds' | 'network' | null
  const [note, setNote] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!email || !password) return setError('creds')
    setLoading(true)
    setError(null)
    try {
      await api.login(email, password)
    } catch (err) {
      setLoading(false)
      setError(err.status ? 'creds' : 'network')
      return
    }
    // Auth succeeded — hand off to App (which fetches the profile and switches screens). Keep the
    // button in its loading state through that brief fetch; App unmounts us when it routes.
    onAuthenticated()
  }

  return (
    <div className="login">
      <div className="hold hold-sm rise">
        <h1 className="serif login-h1">Welcome back.</h1>
        <p className="login-lede">Straight answers about what you can actually afford — no flattery.</p>

        {error && (
          <div className="alert" role="alert">
            <AlertCircle size={18} />
            <span>
              {error === 'creds' ? (
                <><strong>Check your details.</strong> That email and password don’t match an account.</>
              ) : (
                <><strong>Can’t reach the server.</strong> Check your connection and try again.</>
              )}
            </span>
          </div>
        )}

        <form onSubmit={submit}>
          <label className="fld-label" htmlFor="email">Email</label>
          <input
            id="email" className="fld" type="email" autoComplete="email" inputMode="email"
            placeholder="you@email.com" value={email} onChange={(e) => setEmail(e.target.value)}
          />
          <label className="fld-label" htmlFor="password">Password</label>
          <input
            id="password" className="fld" type="password" autoComplete="current-password"
            placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit" className="btn btn-primary login-submit" disabled={loading}>
            {loading ? (<><span className="spinner" />Signing in…</>) : 'Sign in'}
          </button>
        </form>

        <p className="login-foot">
          New here?{' '}
          <a href="#" onClick={(e) => { e.preventDefault(); setNote(true) }}>Create an account</a>
        </p>
        {note && <p className="login-note">Sign-up isn’t available yet — ask the owner to create your account.</p>}
      </div>
    </div>
  )
}
