import { NavLink, useLocation } from 'react-router-dom';
import './Sidebar.css';

const NAV_ITEMS = [
  {
    to: '/',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
    label: 'Dashboard',
  },
  {
    to: '/live',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" x2="12" y1="19" y2="22" />
      </svg>
    ),
    label: 'Live Session',
  },
  {
    to: '/history',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    label: 'History',
  },
  {
    to: '/settings',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
    label: 'Settings',
  },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="sidebar" id="main-sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="7" cy="7" r="2" fill="var(--accent-500)" stroke="none" />
            <circle cx="17" cy="7" r="2" fill="var(--accent-500)" stroke="none" />
            <circle cx="7" cy="13" r="2" fill="var(--accent-400)" stroke="none" />
            <circle cx="17" cy="13" r="2" fill="var(--accent-400)" stroke="none" />
            <circle cx="7" cy="19" r="2" fill="var(--accent-300)" stroke="none" />
            <circle cx="17" cy="19" r="2" fill="var(--accent-300)" stroke="none" />
          </svg>
        </div>
        <div className="sidebar-brand-text">
          <span className="sidebar-title">Sparky</span>
          <span className="sidebar-subtitle">Braille Agent</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'sidebar-link--active' : ''}`
            }
            end={item.to === '/'}
            id={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            <span className="sidebar-link-label">{item.label}</span>
            {item.to === '/live' && (
              <span className="sidebar-link-live-dot" />
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-status">
          <span className="status-dot status-dot--online" />
          <span className="text-sm text-secondary">Agent Online</span>
        </div>
      </div>
    </aside>
  );
}
