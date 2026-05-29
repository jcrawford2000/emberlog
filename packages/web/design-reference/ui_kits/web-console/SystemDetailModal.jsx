/* System detail modal (from SystemHealthCard expanded view) */
function SystemDetailModal({ site, liveCount, onClose }) {
  if (!site) return null;
  const raw = (site.decode_rate_pct / 2.5).toFixed(1);
  const cc = site.control_channel_mhz ? `${site.control_channel_mhz.toFixed(5)} MHz` : "No control channel";
  const interval = site.interval_s != null ? `${site.interval_s.toFixed(1)}s` : "Unknown";
  return (
    <div className="scrim" onClick={onClose}>
      <section className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2 className="modal-title">{site.sys_name}</h2>
            <div className="modal-group">{site.group}</div>
          </div>
          <button className="modal-close" onClick={onClose}>Close</button>
        </div>
        <dl className="dl">
          <div>
            <dt>Decode Rate</dt>
            <dd>{site.decode_rate_pct.toFixed(1)}% <span className="muted" style={{ fontSize: 11, fontWeight: 400 }}>({raw} / 40 raw)</span></dd>
          </div>
          <div><dt>Status</dt><dd style={{ textTransform: "capitalize" }}>{site.status}</dd></div>
          <div><dt>Active Calls</dt><dd>{liveCount}</dd></div>
          <div><dt>System #</dt><dd>{site.sys_num}</dd></div>
          <div><dt>Interval</dt><dd>{interval}</dd></div>
          <div><dt>Sites</dt><dd>{site.sites}</dd></div>
          <div className="col2"><dt>Control Channel</dt><dd className="mono" style={{ fontSize: 13 }}>{cc}</dd></div>
        </dl>
      </section>
    </div>
  );
}
window.SystemDetailModal = SystemDetailModal;
