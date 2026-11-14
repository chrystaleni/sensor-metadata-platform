import { useEffect, useState } from 'react'
import { DEFAULT_PAGE, NAV_ITEMS, pageFromHash } from './navigation'

export function Sidebar({ activePage, onNavigate }) {
  return <aside className="fe-sidebar" aria-label="Main navigation">
    <div className="fe-brand"><span className="fe-logo">SM</span><span><strong>Sensor Metadata</strong><small>MANAGEMENT PLATFORM</small></span></div>
    <div className="fe-nav-label">WORKSPACE</div>
    <nav aria-label="Workspace pages">{NAV_ITEMS.map(({ id, label, icon }) =>
      <a key={id} href={`#/${id}`} onClick={() => onNavigate(id)} className={`fe-nav-item ${activePage === id ? 'active' : ''}`} aria-current={activePage === id ? 'page' : undefined} title={label}>
        <span className="fe-nav-icon" aria-hidden="true">{icon}</span><span className="fe-nav-text">{label}</span>
      </a>)}</nav>
    
  </aside>
}

export function Topbar({ pageLabel }) {
  return <header className="fe-topbar">
    <div className="fe-breadcrumb">Workspace <span>/</span> <strong>{pageLabel}</strong></div>
    <div className="fe-topright"><div className="fe-avatar" aria-label="Preview avatar">SM</div></div>
  </header>
}

export function AppLayout({ children }) {
  const [activePage, setActivePage] = useState(() => typeof window === 'undefined' ? DEFAULT_PAGE : pageFromHash(window.location.hash))
  useEffect(() => {
    const syncPage = () => setActivePage(pageFromHash(window.location.hash))
    window.addEventListener('hashchange', syncPage)
    return () => window.removeEventListener('hashchange', syncPage)
  }, [])
  const current = NAV_ITEMS.find(item => item.id === activePage) || NAV_ITEMS[0]
  const navigate = (id) => setActivePage(id)
  return <div className="fe-shell fe02-shell">
    <a className="fe02-skip" href="#main-content">Skip to content</a>
    <Sidebar activePage={activePage} onNavigate={navigate}/>
    <div className="fe-main">
      <Topbar pageLabel={current.label}/>
      <main id="main-content" className="fe-content" tabIndex="-1">{children({ page: current, navigate })}</main>
      <footer className="fe-footer"><span>Sensor Metadata Management Platform</span></footer>
    </div>
  </div>
}
