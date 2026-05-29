/* Recent Calls table (rich variant from App.tsx) */
function CallRow({ call, onSelectSystem }) {
  const recorded = typeof call.rec_num === "number" && call.rec_num >= 0;
  return (
    <tr className={call.isActive ? "live" : ""}>
      <td>
        <span className="state">
          <span className="dot" style={{ background: call.isActive ? "#FF6B00" : "#7A7A7A" }}></span>
          {call.isActive ? "Live" : "Ended"}
        </span>
      </td>
      <td style={{ whiteSpace: "nowrap" }}>
        <div className="cell-stack">
          <span>{fmtDateTime(call.started_at)}</span>
          <span className="mono muted">{fmtElapsed(call.elapsed_s)}</span>
        </div>
      </td>
      <td>
        <button className="sys-btn" onClick={() => onSelectSystem(call.sys_name)}>
          <Icon name="tower-control" />{call.sys_name}
        </button>
      </td>
      <td>
        <div className="tags">
          <span style={{ fontWeight: 600 }}>{call.talkgroup || call.talkgroup_id || "Unknown talkgroup"}</span>
          {call.encrypted && <span className="flag enc"><Icon name="lock" />ENC</span>}
          {recorded && <span className="flag rec"><Icon name="radio" />REC</span>}
          {call.emergency && <span className="pill">Emergency</span>}
          {call.phase2_tdma && <span className="pill">TDMA{call.tdma_slot != null ? ` ${call.tdma_slot}` : ""}</span>}
        </div>
        <div className="mono muted" style={{ marginTop: 4 }}>tg {call.talkgroup_id}</div>
      </td>
      <td>
        <div className="cell-stack">
          <span>{call.description || "No description"}</span>
          <span className="muted" style={{ fontSize: 11.5 }}>{[call.category, call.tag].filter(Boolean).join(" • ") || "No category"}</span>
        </div>
      </td>
      <td>
        <div className="cell-stack">
          <span className="mono">{fmtFreq(call.freq_mhz)}</span>
          <span className="mono muted">SRC {call.src_num ?? "?"} • REC {call.rec_num >= 0 ? call.rec_num : "?"}</span>
        </div>
      </td>
    </tr>
  );
}

function CallsTable({ calls, visibleCount, activeNow, selectedSystem, onSelectSystem, loading }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">Recent Calls</div>
          <div className="panel-sub">{selectedSystem ? `${selectedSystem} selected` : "All systems"}</div>
        </div>
        <div className="panel-meta">
          <span>{visibleCount} visible</span>
          <span>{activeNow} active now</span>
        </div>
      </div>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>State</th><th>Started</th><th>System</th><th>Talkgroup</th><th>Details</th><th>RF</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((c) => <CallRow key={c.id} call={c} onSelectSystem={onSelectSystem} />)}
            {calls.length === 0 && (
              <tr><td colSpan={6} className="empty">{loading ? "Loading traffic dashboard…" : "No calls match the current filters."}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

Object.assign(window, { CallsTable, CallRow });
