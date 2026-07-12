import { ChatTab, BarsTab } from '../lib/icons'

export default function BottomNav({ screen, onNavigate }) {
  return (
    <nav className="bottom-nav">
      <button className={screen === 'chat' ? 'active' : ''} onClick={() => onNavigate('chat')}>
        <ChatTab size={23} />
        Chat
      </button>
      <button className={screen === 'numbers' ? 'active' : ''} onClick={() => onNavigate('numbers')}>
        <BarsTab size={23} />
        Your Numbers
      </button>
    </nav>
  )
}
