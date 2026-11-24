import { useEffect, useRef, useState } from 'react'
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

const ROLE_LABELS = { VIEWER: 'Viewer', EDITOR: 'Editor', DEPARTMENT_ADMIN: 'Department Administrator', SYSTEM_ADMIN: 'System Administrator' }

function ProfileMenu({ profile }) {
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const close = (event) => { if (event.type === 'keydown' ? event.key === 'Escape' : !box.current?.contains(event.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close) }
  }, [open])
  const name = profile?.username || ''
  const initials = (name.slice(0, 2) || 'SM').toUpperCase()
  if (!profile) return <div className="fe-avatar" aria-hidden="true">{initials}</div>
  return <div className="fe-profile" ref={box}>
    <button type="button" className="fe-avatar" aria-label="Profile menu" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(v => !v)}>{initials}</button>
    {open && <div className="fe-profile-card" role="dialog" aria-label="Your profile">
      <div className="fe-profile-head"><span className="fe-avatar big" aria-hidden="true">{initials}</span>
        <span><strong>{name}</strong><small>{ROLE_LABELS[profile.role] || 'No role assigned'}</small></span></div>
      {profile.departments?.length > 0 && <label className="fe-profile-dept">Department
        <select aria-label="Switch department" value={profile.department} onChange={e => profile.onDepartment(e.target.value)}>
          <option value="">Select authorized Department…</option>
          {profile.departments.map(d => <option key={d.id} value={d.id}>{d.organisation} / {d.name}</option>)}
        </select></label>}
      <button type="button" className="fe-profile-logout" onClick={profile.onLogout}>Log out</button>
    </div>}
  </div>
}

export function Topbar({ pageLabel, profile }) {
  return <header className="fe-topbar">
    <div className="fe-breadcrumb">Workspace <span>/</span> <strong>{pageLabel}</strong></div>
    <div className="fe-topright"><ProfileMenu profile={profile}/></div>
  </header>
}

export function AppLayout({ children, profile }) {
  const mainRef = useRef(null)
  const [activePage, setActivePage] = useState(() => typeof window === 'undefined' ? DEFAULT_PAGE : pageFromHash(window.location.hash))
  useEffect(() => {
    const syncPage = () => setActivePage(pageFromHash(window.location.hash))
    window.addEventListener('hashchange', syncPage)
    return () => window.removeEventListener('hashchange', syncPage)
  }, [])
  const current = NAV_ITEMS.find(item => item.id === activePage) || NAV_ITEMS[0]
  const navigate = (id) => setActivePage(id)
  const skipToContent = (event) => {
    event.preventDefault()
    mainRef.current?.focus()
  }
  return <div className="fe-shell fe02-shell">
    <a className="fe02-skip" href="#main-content" onClick={skipToContent}>Skip to content</a>
    <Sidebar activePage={activePage} onNavigate={navigate}/>
    <div className="fe-main">
      <Topbar pageLabel={current.label} profile={profile}/>
      <main ref={mainRef} id="main-content" className="fe-content" tabIndex="-1">{children({ page: current, navigate })}</main>
      <footer className="fe-footer"><span>Sensor Metadata Management Platform</span></footer>
    </div>
  </div>
}
