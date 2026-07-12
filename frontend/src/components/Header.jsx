import { Wave, Sun, Moon, LogOut } from '../lib/icons'

export default function Header({ isDark, onToggleTheme, authed, onLogout }) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand">
          <span className="brand-badge">
            <Wave size={15} color="#fff" />
          </span>
          <span className="brand-name serif">Floated</span>
        </div>
        <div className="head-actions">
          {authed && (
            <button className="theme-btn" onClick={onLogout} aria-label="Sign out" title="Sign out">
              <LogOut size={18} />
            </button>
          )}
          <button className="theme-btn" onClick={onToggleTheme} aria-label="Toggle color theme">
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </div>
    </header>
  )
}
