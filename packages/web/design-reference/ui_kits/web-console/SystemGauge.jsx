/* Radial decode-rate gauge (SystemHealthCard) + the responsive strip */
function SystemGauge({ site, liveCount, selected, onSelect, onDetails }) {
  const accent = statusAccent(site.status);
  const clamped = Math.max(0, Math.min(100, site.decode_rate_pct));
  const ring = `conic-gradient(${accent} ${clamped * 3.6}deg, rgba(255,255,255,0.16) 0deg)`;
  return (
    <div className="gauge-cell">
      <button
        className={`gauge ${selected ? "sel" : ""}`}
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`Filter recent calls for ${site.sys_name}`}
      >
        <div className="gauge-ring" style={{ background: ring }}>
          <div className="gauge-well">
            <div className="gauge-sys">{site.key}</div>
            <div className="gauge-rate" title={`Raw: ${(site.decode_rate_pct / 2.5).toFixed(1)} / 40`}>
              {site.decode_rate_pct.toFixed(1)}% <Icon name="info" />
            </div>
            <span className="gauge-live"><Icon name="radio" />{liveCount} Live</span>
          </div>
        </div>
      </button>
      <div className="gauge-actions">
        <button className={`chip-btn ${selected ? "sel" : ""}`} onClick={onSelect}>
          <Icon name="search" />{selected ? "Showing Filter" : "Filter Calls"}
        </button>
        <button className="chip-btn" onClick={onDetails}>Details</button>
      </div>
    </div>
  );
}

function SystemGaugeStrip({ sites, liveCountBySystem, selected, onSelect, onDetails }) {
  return (
    <div className="section">
      <div className="section-eyebrow">System Health</div>
      <div className="gauge-grid">
        {sites.map((s) => (
          <SystemGauge
            key={s.key}
            site={s}
            liveCount={liveCountBySystem[s.sys_name] || 0}
            selected={selected === s.sys_name}
            onSelect={() => onSelect(s.sys_name)}
            onDetails={() => onDetails(s)}
          />
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { SystemGauge, SystemGaugeStrip });
