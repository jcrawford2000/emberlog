/* Page heading + connection status (TrafficHeader) and the filter bar */
function PageHead({ connection, lastFetch }) {
  const connMap = {
    live:         { label: "Live",         color: "#BEF264", pulse: true },
    reconnecting: { label: "Reconnecting", color: "#FCD34D" },
    connecting:   { label: "Connecting",   color: "#7DD3FC" },
    offline:      { label: "Offline",      color: "#FDA4AF" },
  };
  const c = connMap[connection] || connMap.live;
  return (
    <div className="page-head">
      <div>
        <h1 className="h1">Traffic Monitor</h1>
        <div className="page-sub">Snapshot from /api/v1/traffic/summary + live updates from /api/v1/sse</div>
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        <span className="conn">
          <span className={`dot ${c.pulse ? "pulse" : ""}`} style={{ background: c.color }}></span>
          {c.label}
        </span>
        <span className="conn-meta">Last fetch: {lastFetch}</span>
      </div>
    </div>
  );
}

function FilterBar({ search, onSearch, hideEnc, onHideEnc, onClear, canClear }) {
  return (
    <div className="filters">
      <input
        className="input"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search talkgroup, category, tag, or system"
      />
      <label className="check">
        <input type="checkbox" checked={hideEnc} onChange={(e) => onHideEnc(e.target.checked)} />
        Hide encrypted
      </label>
      <button className="btn-ghost" onClick={onClear} disabled={!canClear}>Clear filters</button>
    </div>
  );
}

Object.assign(window, { PageHead, FilterBar });
