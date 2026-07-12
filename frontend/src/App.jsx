import { useEffect, useState } from 'react'
import './App.css'
import * as api from './lib/api'
import Header from './components/Header'
import BottomNav from './components/BottomNav'
import Login from './screens/Login'
import Onboarding from './screens/Onboarding'
import Chat from './screens/Chat'
import Numbers from './screens/Numbers'

const THEME_KEY = 'floated-theme'

export default function App() {
  // Explicit theme choice persists and beats the OS preference (null = follow OS).
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || null)
  const [authed, setAuthed] = useState(false)
  const [screen, setScreen] = useState('chat') // meaningful only when authed

  useEffect(() => {
    const root = document.documentElement
    if (theme) {
      root.dataset.theme = theme
      localStorage.setItem(THEME_KEY, theme)
    } else {
      delete root.dataset.theme
      localStorage.removeItem(THEME_KEY)
    }
  }, [theme])

  // A 401 anywhere drops us back to login (token already cleared in the API layer).
  useEffect(() => {
    api.setOnLogout(() => setAuthed(false))
  }, [])

  const isDark = theme ? theme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches
  const toggleTheme = () => setTheme(isDark ? 'light' : 'dark')

  // After a successful sign-in, the profile decides the landing screen: none → onboarding, else chat.
  async function afterAuth() {
    let profile = null
    try {
      profile = await api.getProfile()
    } catch (e) {
      if (e.status === 401) return // logged out
      // transient error: let them in and default to chat (screens surface their own load errors)
    }
    setScreen(profile ? 'chat' : 'onboarding')
    setAuthed(true)
  }

  function logout() {
    api.clearToken()
    setAuthed(false)
  }

  return (
    <div className="app">
      <div className="shell">
        <Header isDark={isDark} onToggleTheme={toggleTheme} authed={authed} onLogout={logout} />
        <div className="screen-wrap">
          {!authed && <Login onAuthenticated={afterAuth} />}
          {authed && screen === 'onboarding' && <Onboarding onFinished={() => setScreen('chat')} />}
          {authed && screen === 'chat' && <Chat />}
          {authed && screen === 'numbers' && <Numbers />}
        </div>
        {authed && screen !== 'onboarding' && <BottomNav screen={screen} onNavigate={setScreen} />}
      </div>
    </div>
  )
}
