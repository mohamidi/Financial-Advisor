import { useState } from 'react'
import './Login.css'
import { AlertCircle, Mail } from '../lib/icons'
import * as api from '../lib/api'

const MIN_PASSWORD_LEN = 6 // mirrors Supabase's own minimum; caught here first to avoid a round trip

// Real Supabase auth: on success App fetches the profile and routes (onboarding vs chat).
export default function Login({ onAuthenticated }) {
  const [mode, setMode] = useState('login') // 'login' | 'signup' | 'check-email'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null) // 'creds' | 'network' | 'weak' | 'mismatch' | 'signup-failed' | null

  function switchMode(next) {
    setMode(next)
    setError(null)
    setPassword('')
    setConfirmPassword('')
  }

  async function submitLogin(e) {
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

  async function submitSignup(e) {
    e.preventDefault()
    if (!email || !password || !confirmPassword) return setError('creds')
    if (password.length < MIN_PASSWORD_LEN) return setError('weak')
    if (password !== confirmPassword) return setError('mismatch')
    setLoading(true)
    setError(null)
    try {
      await api.signup(email, password)
    } catch (err) {
      setLoading(false)
      setError(err.detail || 'signup-failed')
      return
    }
    setLoading(false)
    setMode('check-email')
  }

  if (mode === 'check-email') {
    return (
      <div className="login">
        <div className="hold hold-sm rise">
          <span className="login-mail"><Mail size={26} color="var(--accent)" /></span>
          <h1 className="serif login-h1">Check your email.</h1>
          <p className="login-lede">
            We sent a confirmation link to <strong>{email}</strong>. Click it, then come back and log in.
          </p>
          <button type="button" className="btn btn-primary login-submit" onClick={() => switchMode('login')}>
            Back to login
          </button>
        </div>
      </div>
    )
  }

  const signingUp = mode === 'signup'

  return (
    <div className="login">
      <div className="hold hold-sm rise">
        <h1 className="serif login-h1">{signingUp ? 'Create your account.' : 'Welcome back.'}</h1>
        <p className="login-lede">Straight answers about what you can actually afford — no flattery.</p>

        {error && (
          <div className="alert" role="alert">
            <AlertCircle size={18} />
            <span>
              {error === 'creds' && !signingUp && (
                <><strong>Check your details.</strong> That email and password don’t match an account.</>
              )}
              {error === 'creds' && signingUp && (
                <><strong>Missing details.</strong> Fill in every field to create an account.</>
              )}
              {error === 'weak' && (
                <><strong>Password too short.</strong> Use at least {MIN_PASSWORD_LEN} characters.</>
              )}
              {error === 'mismatch' && (
                <><strong>Passwords don’t match.</strong> Double-check both fields.</>
              )}
              {error === 'network' && (
                <><strong>Can’t reach the server.</strong> Check your connection and try again.</>
              )}
              {error !== 'creds' && error !== 'weak' && error !== 'mismatch' && error !== 'network' && (
                <><strong>Couldn’t create your account.</strong> {error === 'signup-failed' ? 'Please try again.' : error}</>
              )}
            </span>
          </div>
        )}

        <form onSubmit={signingUp ? submitSignup : submitLogin}>
          <label className="fld-label" htmlFor="email">Email</label>
          <input
            id="email" className="fld" type="email" autoComplete="email" inputMode="email"
            placeholder="you@email.com" value={email} onChange={(e) => setEmail(e.target.value)}
          />
          <label className="fld-label" htmlFor="password">Password</label>
          <input
            id="password" className="fld" type="password"
            autoComplete={signingUp ? 'new-password' : 'current-password'}
            placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)}
          />
          {signingUp && (
            <>
              <label className="fld-label" htmlFor="confirm-password">Confirm password</label>
              <input
                id="confirm-password" className="fld" type="password" autoComplete="new-password"
                placeholder="••••••••" value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </>
          )}
          <button type="submit" className="btn btn-primary login-submit" disabled={loading}>
            {loading
              ? (<><span className="spinner" />{signingUp ? 'Creating account…' : 'Signing in…'}</>)
              : (signingUp ? 'Create account' : 'Sign in')}
          </button>
        </form>

        <p className="login-foot">
          {signingUp ? (
            <>Already have an account?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); switchMode('login') }}>Log in</a>
            </>
          ) : (
            <>New here?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); switchMode('signup') }}>Create an account</a>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
