/* Dispatch Intelligence page — filterable live incident feed + detail (Direction A). */
function dispMatchesQuery(inc, q) {
  if (!q) return true;
  const s = q.trim().toLowerCase();
  return [inc.address, inc.incident_type, inc.transcript, inc.channel, inc.units.join(" "), citiesOfIncident(inc).join(" ")]
    .some((v) => (v || "").toLowerCase().includes(s));
}
function dispWithinTime(inc, time) {
  if (time === "all") return true;
  const age = (NOW - new Date(inc.dispatched_at).getTime()) / 1000;
  if (time === "live") return age <= 120;
  if (time === "1h") return age <= 3600;
  if (time === "4h") return age <= 14400;
  return true;
}
function dispPasses(inc, f) {
  if (!dispMatchesQuery(inc, f.q)) return false;
  if (!dispWithinTime(inc, f.time)) return false;
  if (f.cities.length && !citiesOfIncident(inc).some((c) => f.cities.includes(c))) return false;
  if (f.units.length && !inc.units.some((u) => f.units.includes(u))) return false;
  if (f.types.length && !f.types.includes(inc.incident_type)) return false;
  if (f.cats.length && !f.cats.includes(catOf(inc.incident_type))) return false;
  if (f.channels.length && !f.channels.includes(inc.channel)) return false;
  return true;
}

function DispatchPage() {
  const [filters, setFilters] = React.useState({ q: "", time: "all", cities: [], units: [], types: [], cats: [], channels: [] });
  const [openPop, setOpenPop] = React.useState(null);
  const [sel, setSel] = React.useState(INCIDENTS[0].id);
  const [raw, setRaw] = React.useState(false);

  const filtered = INCIDENTS.filter((i) => dispPasses(i, filters));
  const selInc = filtered.find((i) => i.id === sel) || filtered[0] || null;

  return (
    <div className="dispatch">
      {/* page head */}
      <div className="phead">
        <div>
          <h1 className="h1">Dispatch Intelligence</h1>
          <div className="psub">Structured incidents from emberlog-transcriber · live over /api/v1/sse</div>
        </div>
        <span className="conn"><span className="dot pulse" style={{ background: "#BEF264" }}></span>Live · Phoenix Regional</span>
      </div>

      {/* KPI strip */}
      <div className="kpis">
        <div className="kpi"><div className="klabel">Incidents · 1h</div><div className="kval">{INCIDENTS.length}</div><div className="kfoot">3 in last 5 min</div></div>
        <div className="kpi"><div className="klabel">Active units</div><div className="kval">14</div><div className="kfoot">{ACTIVE_CITIES.length} cities</div></div>
        <div className="kpi"><div className="klabel">Special calls</div><div className="kval" style={{ color: "#ff7a5c" }}>2</div><div className="kfoot">last 1h</div></div>
        <div className="kpi"><div className="klabel">Top category</div><div className="kval" style={{ fontSize: 18, paddingTop: 4 }}>EMS · 5</div><div className="kfoot">Fire 3 · MVC 2</div></div>
      </div>

      {/* filter toolbar */}
      <DispatchFilterBar filters={filters} setFilters={setFilters} resultCount={filtered.length} total={INCIDENTS.length} openPop={openPop} setOpenPop={setOpenPop} />

      {/* master-detail */}
      <div className="dgrid">
        {/* feed */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="eyebrow" style={{ marginBottom: 2 }}>Live Feed · {filtered.length} shown</div>
          {filtered.map((i) => {
            const st = typeStyle(i.incident_type);
            return (
              <button key={i.id} className={`inc ${selInc && i.id === selInc.id ? "sel" : ""} ${i.id === INCIDENTS[0].id ? "new" : ""}`}
                style={{ borderLeftColor: st.accent }} onClick={() => setSel(i.id)}>
                <div className="inc-top">
                  <span className="tbadge" style={{ background: st.tint, color: st.accent }}><Icon name={st.icon} size={13} />{i.incident_type}</span>
                  {i.special_call && <span className="special"><Icon name="siren" size={12} />SPECIAL</span>}
                  <span className="itime">{relAgo(i.dispatched_at)}</span>
                </div>
                <div className="iaddr">{i.address}</div>
                <div className="imeta">
                  <span className="chip"><Icon name="building-2" size={12} />{citiesOfIncident(i).join(" · ")}</span>
                  <span className="chip ch"><Icon name="radio" size={12} />{i.channel}</span>
                  {i.units.map((u) => <span key={u} className="chip"><Icon name="truck" size={12} />{u}</span>)}
                </div>
              </button>
            );
          })}
          {filtered.length === 0 ? (
            <div style={{ padding: "40px 16px", textAlign: "center", color: "var(--el-slate-400)", border: "1px dashed var(--el-line-20)", borderRadius: 12, fontSize: 13.5 }}>
              No incidents match these filters.
            </div>
          ) : null}
        </div>

        {/* detail */}
        {selInc ? <DispatchDetail inc={selInc} raw={raw} setRaw={setRaw} /> : (
          <div className="detail" style={{ alignItems: "center", justifyContent: "center", minHeight: 280, color: "var(--el-slate-400)" }}>
            Select an incident to see its transcript and details.
          </div>
        )}
      </div>
    </div>
  );
}

function DispatchDetail({ inc, raw, setRaw }) {
  const st = typeStyle(inc.incident_type);
  return (
    <div className="detail">
      <div className="d-head">
        <div>
          <span className="d-type" style={{ background: st.tint, color: st.accent }}><Icon name={st.icon} size={14} />{catOf(inc.incident_type)} · {inc.incident_type}</span>
          <div className="d-addr">{inc.address}</div>
          <div className="d-time">Dispatched {clock(inc.dispatched_at)} · {relAgo(inc.dispatched_at)} · incident #{inc.id}</div>
        </div>
        {inc.special_call && <span className="special" style={{ fontSize: 12, padding: "5px 11px" }}><Icon name="siren" size={13} />SPECIAL CALL</span>}
      </div>

      <div className="dtop">
        <div className="fields">
          <div className="field"><dt>City</dt><dd style={{ fontSize: 13 }}>{citiesOfIncident(inc).join(", ")}</dd></div>
          <div className="field"><dt>Channel</dt><dd style={{ fontFamily: "var(--el-font-mono)", fontSize: 13 }}>{inc.channel}</dd></div>
          <div className="field" style={{ gridColumn: "span 2" }}><dt>Units</dt><dd>{inc.units.map((u) => <span key={u} className="unit"><Icon name="truck" size={12} />{u} <span style={{ color: "var(--el-slate-400)", fontWeight: 400, fontSize: 11 }}>· {cityOfUnit(u)}</span></span>)}</dd></div>
        </div>
        <MapPin accent={st.accent} address={inc.address} height={150} />
      </div>

      {/* audio */}
      <div className="audio">
        <div className="slabel">Audio · segment</div>
        <div className="a-row">
          <button className="a-play" style={{ background: st.accent }}><Icon name="play" size={18} /></button>
          <div style={{ flex: 1 }}>
            <Waveform accent={st.accent} played={0.34} seed={inc.id} />
            <div className="a-time"><span>0:00</span><span>call_{inc.id}628.wav</span><span>0:08</span></div>
          </div>
        </div>
      </div>

      {/* transcript */}
      <div>
        <div className="slabel"><span>Transcript</span>
          <span className="seg"><button className={!raw ? "on" : ""} onClick={() => setRaw(false)}>Cleaned</button><button className={raw ? "on" : ""} onClick={() => setRaw(true)}>Raw STT</button></span>
        </div>
        <div className={`trans ${raw ? "raw" : ""}`}>{raw ? inc.original_text : inc.transcript}</div>
      </div>

      {/* correlation + source */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <span className="corr"><Icon name="link" size={14} />Linked call · {inc.correlation.system} · <span className="mono">tg {inc.correlation.tg}</span><Icon name="arrow-up-right" size={14} /></span>
        <span className="src">emberlog-transcriber · {inc.correlation.system}</span>
      </div>
    </div>
  );
}

Object.assign(window, { DispatchPage, DispatchDetail });
