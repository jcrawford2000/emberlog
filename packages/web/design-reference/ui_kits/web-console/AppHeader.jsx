/* App header: fire-engine-red sticky bar with brand mark, domain nav, connection pill.
   Traffic + Dispatch are live tabs (driven by `active`/`onNavigate`); others are stubbed. */
function AppHeader({ active = "traffic", onNavigate }) {
  const navItems = [
    { id: "traffic", label: "Traffic" },
    { id: "systems", label: "Systems", soon: true },
    { id: "dispatch", label: "Dispatch" },
    { id: "scanner", label: "Scanner", soon: true },
    { id: "command", label: "Command", soon: true },
  ];
  return (
    <header className="hdr">
      <div className="hdr-in">
        <div className="brand">
          <div className="brand-tile"><Icon name="audio-lines" size={26} /></div>
          <div>
            <div className="brand-name">Emberlog</div>
            <div className="brand-sub">Platform Operations Console</div>
          </div>
        </div>
        <nav className="nav">
          {navItems.map((n) => (
            <a key={n.id}
              className={`nav-link ${active === n.id ? "active" : ""} ${n.soon ? "soon" : ""}`}
              onClick={() => { if (!n.soon && onNavigate) onNavigate(n.id); }}>
              {n.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
window.AppHeader = AppHeader;
