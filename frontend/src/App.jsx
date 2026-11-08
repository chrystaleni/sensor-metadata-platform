const domains = ['Measurements', 'Physical Devices', 'Network Elements']

function App() {
  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="Sensor Metadata Platform home">
          <span className="wordmark-icon" aria-hidden="true">S</span>
          <span>Sensor Metadata Platform</span>
        </a>
        <span className="status-pill">
          <span className="status-dot" aria-hidden="true" />
          Frontend initialized
        </span>
      </header>

      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">HMY317 · University of Cyprus · KIOS CoE</p>
        <h1 id="page-title" aria-label="Sensor Metadata Management Platform">
          Sensor Metadata<br />Management Platform
        </h1>
        <p className="subtitle">
          Metadata management for Measurements, Physical Devices, and Network Elements
        </p>
        <div className="domain-list" aria-label="Metadata domains">
          {domains.map((domain, index) => (
            <div className="domain-card" key={domain}>
              <span className="domain-number">0{index + 1}</span>
              <span>{domain}</span>
              <span className="domain-arrow" aria-hidden="true">↗</span>
            </div>
          ))}
        </div>
      </section>

      <footer className="footer">
        <span>Platform foundation</span>
        <span>React + Vite</span>
      </footer>
    </main>
  )
}

export default App
