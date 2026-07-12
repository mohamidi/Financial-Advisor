// Single API layer. The access token lives in memory only (never localStorage) so an XSS can't lift
// a persisted token — the tradeoff is re-login on refresh, matching the design's security note. A
// 401 anywhere clears the token and fires onLogout so the app drops back to the login screen.

let token = null
let config = null
let onLogout = () => {}

export function setOnLogout(fn) { onLogout = fn }
export function clearToken() { token = null }

async function loadConfig() {
  if (config) return config
  const r = await fetch('/config')
  if (!r.ok) throw new Error('Could not load config')
  config = await r.json()
  return config
}

// Signs in directly against Supabase Auth (not our backend) and keeps the returned JWT in memory.
export async function login(email, password) {
  const cfg = await loadConfig()
  const r = await fetch(`${cfg.supabase_url}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { apikey: cfg.supabase_publishable_key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!r.ok) {
    const e = new Error('Login failed')
    e.status = r.status // Supabase returns 400 for bad credentials
    throw e
  }
  token = (await r.json()).access_token
}

async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (r.status === 401) {
    clearToken()
    onLogout()
    const e = new Error('Unauthorized')
    e.status = 401
    throw e
  }
  return r
}

export async function getProfile() {
  const r = await api('/profile')
  if (!r.ok) throw new Error('profile')
  return (await r.json()).profile
}

export async function getQuestions() {
  const r = await api('/onboarding/questions')
  if (!r.ok) throw new Error('questions')
  return (await r.json()).questions
}

export async function submitOnboarding(answers) {
  const r = await api('/onboarding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
  if (r.status === 422) {
    const e = new Error('validation')
    e.status = 422
    e.errors = (await r.json()).detail?.errors || {}
    throw e
  }
  if (!r.ok) throw new Error('onboarding')
  return (await r.json()).profile
}

export async function sendChat(history, message) {
  const r = await api('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history, message }),
  })
  if (r.status === 429) {
    const e = new Error('rate limited')
    e.status = 429
    e.detail = (await r.json()).detail
    throw e
  }
  if (!r.ok) throw new Error('chat')
  return await r.json() // { reply, history, verdict }
}

export async function getSummary() {
  const r = await api('/summary')
  if (!r.ok) {
    const e = new Error('summary')
    e.status = r.status
    throw e
  }
  return await r.json()
}
