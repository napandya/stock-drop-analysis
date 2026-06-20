// Sidebar: brand mark, section navigation, run-all action and a live backend
// health indicator. Nav items are real <button>s inside a <nav> so keyboard and
// screen-reader users get proper semantics and focus order.
export function Sidebar({ sections, activeKey, onSelect, onRunAll, running, health }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <svg className="spark" viewBox="0 0 220 34" preserveAspectRatio="none" aria-hidden="true">
          <polyline
            points="0,8 30,12 55,9 80,16 105,14 130,22 160,19 185,28 220,31"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
          />
          <circle cx="220" cy="31" r="3.5" fill="var(--danger)" />
        </svg>
        <div className="name">Drop-Driver Analysis</div>
        <div className="sub">ITS 836 · Big Data Analytics</div>
      </div>

      <nav className="nav" aria-label="Analyses">
        <p className="nav-label" id="nav-label">
          Analyses
        </p>
        <ul aria-labelledby="nav-label">
          {sections.map((s, i) => (
            <li key={s.key}>
              <button
                type="button"
                className={`nav-item${activeKey === s.key ? " active" : ""}`}
                aria-current={activeKey === s.key ? "true" : undefined}
                onClick={() => onSelect(s.key)}
              >
                <span className="idx" aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{s.title.replace(/^Member \d+ -- /, "")}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <button type="button" className="run-all" onClick={onRunAll} disabled={running}>
        {running ? "Running…" : "Run full analysis"}
      </button>

      <div className="health">
        <span className={`dot ${health.state}`} aria-hidden="true" />
        <span>{health.text}</span>
      </div>
    </aside>
  );
}
