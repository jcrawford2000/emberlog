/* Dispatch filter system: time, city (unit-range), units, incident type, category, channel.
   Renamed to DispatchFilterBar so it doesn't collide with the Traffic FilterBar. */

function FilterPopover({ id, label, count, openPop, setOpenPop, children, align }) {
  const on = openPop === id;
  return (
    <div className="ftrigger">
      <button className={`ftbtn ${count ? "on" : ""}`} onClick={() => setOpenPop(on ? null : id)}>
        {label}
        {count ? <span className="count">{count}</span> : null}
        <Icon name="chevron-down" className="chev" size={14} />
      </button>
      {on ? <div className={`pop ${align === "right" ? "right" : ""}`}>{children}</div> : null}
    </div>
  );
}

function CheckOpt({ selected, onClick, label, sub, dot }) {
  return (
    <button className={`opt ${selected ? "sel" : ""}`} onClick={onClick}>
      <span className="box"><Icon name="check" size={11} /></span>
      {dot ? <span className="dotc" style={{ background: dot }}></span> : null}
      <span>{label}</span>
      {sub ? <span className="sub">{sub}</span> : null}
    </button>
  );
}

function DispatchFilterBar({ filters, setFilters, resultCount, total, openPop, setOpenPop }) {
  const [unitQuery, setUnitQuery] = React.useState("");
  const [cityQuery, setCityQuery] = React.useState("");
  const toggle = (key, val) => setFilters((f) => {
    const has = f[key].includes(val);
    return { ...f, [key]: has ? f[key].filter((x) => x !== val) : [...f[key], val] };
  });
  const clearKey = (key, val) => setFilters((f) => ({ ...f, [key]: f[key].filter((x) => x !== val) }));
  const setTime = (v) => setFilters((f) => ({ ...f, time: v }));
  const clearAll = () => setFilters({ q: "", time: "all", cities: [], units: [], types: [], cats: [], channels: [] });

  const timeOpts = [
    { v: "all", label: "All time" },
    { v: "live", label: "Live · last 2 min" },
    { v: "1h", label: "Last hour" },
    { v: "4h", label: "Last 4 hours" },
  ];
  const timeLabel = timeOpts.find((t) => t.v === filters.time).label;

  // City list: show agencies present in current data first; reveal all 58 on search.
  const citiesShown = (cityQuery.trim()
    ? ALL_CITIES.filter((c) => c.toLowerCase().includes(cityQuery.toLowerCase()))
    : [...ACTIVE_CITIES, ...ALL_CITIES.filter((c) => !ACTIVE_CITIES.includes(c))]);
  const unitsShown = ALL_UNITS.filter((u) => u.toLowerCase().includes(unitQuery.toLowerCase()));

  // active chips
  const chips = [];
  filters.cats.forEach((v) => chips.push({ k: "Category", v, key: "cats" }));
  filters.types.forEach((v) => chips.push({ k: "Type", v, key: "types" }));
  filters.cities.forEach((v) => chips.push({ k: "City", v, key: "cities" }));
  filters.units.forEach((v) => chips.push({ k: "Unit", v, key: "units" }));
  filters.channels.forEach((v) => chips.push({ k: "Channel", v, key: "channels" }));
  if (filters.time !== "all") chips.push({ k: "Time", v: timeLabel, key: "time" });
  const anyActive = chips.length > 0 || filters.q;

  return (
    <div className="ftbar">
      {openPop ? <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setOpenPop(null)} /> : null}

      {/* row 1: search + dropdown filters */}
      <div className="ftrow">
        <div className="fsearch">
          <Icon name="search" size={15} />
          <input value={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} placeholder="Search address, unit, transcript…" />
        </div>

        <FilterPopover id="time" label={<span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Icon name="clock" className="lead" size={14} /> {filters.time === "all" ? "Time" : timeLabel}</span>}
          count={0} openPop={openPop} setOpenPop={setOpenPop}>
          <div className="pop-scroll">
            {timeOpts.map((t) => (
              <button key={t.v} className={`opt ${filters.time === t.v ? "sel" : ""}`} onClick={() => { setTime(t.v); setOpenPop(null); }}>
                <span className="radio"></span><span>{t.label}</span>
              </button>
            ))}
          </div>
        </FilterPopover>

        <FilterPopover id="city" label={<span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Icon name="building-2" className="lead" size={14} /> City</span>}
          count={filters.cities.length} openPop={openPop} setOpenPop={setOpenPop}>
          <input className="pop-search" value={cityQuery} onChange={(e) => setCityQuery(e.target.value)} placeholder="Search all agencies…" />
          <div className="pop-scroll">
            {citiesShown.map((c) => (
              <CheckOpt key={c} selected={filters.cities.includes(c)} onClick={() => toggle("cities", c)} label={c} sub={agencyRange(c)} />
            ))}
          </div>
          <div className="pop-foot"><span style={{ fontSize: 11, color: "var(--el-slate-400)" }}>by unit-number block</span>
            {filters.cities.length ? <button onClick={() => setFilters((f) => ({ ...f, cities: [] }))}>Clear</button> : <span />}</div>
        </FilterPopover>

        <FilterPopover id="units" label={<span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Icon name="truck" className="lead" size={14} /> Units</span>}
          count={filters.units.length} openPop={openPop} setOpenPop={setOpenPop}>
          <input className="pop-search" value={unitQuery} onChange={(e) => setUnitQuery(e.target.value)} placeholder="Filter units…" />
          <div className="pop-scroll">
            {unitsShown.map((u) => (
              <CheckOpt key={u} selected={filters.units.includes(u)} onClick={() => toggle("units", u)} label={u} sub={cityOfUnit(u)} />
            ))}
            {unitsShown.length === 0 ? <div style={{ padding: "10px", fontSize: 12, color: "var(--el-slate-400)" }}>No units</div> : null}
          </div>
        </FilterPopover>

        <FilterPopover id="types" label={<span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Icon name="tags" className="lead" size={14} /> Type</span>}
          count={filters.types.length} openPop={openPop} setOpenPop={setOpenPop}>
          <div className="pop-scroll">
            {ALL_TYPES.map((t) => (
              <CheckOpt key={t} selected={filters.types.includes(t)} onClick={() => toggle("types", t)} label={t} sub={catOf(t)} dot={typeStyle(t).accent} />
            ))}
          </div>
        </FilterPopover>

        <FilterPopover id="channels" label={<span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Icon name="radio" className="lead" size={14} /> Channel</span>}
          count={filters.channels.length} openPop={openPop} setOpenPop={setOpenPop} align="right">
          <div className="pop-scroll">
            {ALL_CHANNELS.map((c) => (
              <CheckOpt key={c} selected={filters.channels.includes(c)} onClick={() => toggle("channels", c)} label={c} />
            ))}
          </div>
        </FilterPopover>
      </div>

      {/* row 2: category quick-chips + count */}
      <div className="ftrow">
        <div className="catrow">
          {ALL_CATS.map((c) => {
            const on = filters.cats.includes(c);
            const st = CAT[c];
            return (
              <button key={c} className="catchip" onClick={() => toggle("cats", c)}
                style={on ? { background: st.tint, borderColor: st.accent, color: st.accent } : null}>
                <span className="cdot" style={{ background: st.accent }}></span>{c}
              </button>
            );
          })}
        </div>
        <span className="fcount">{resultCount} of {total} incidents</span>
      </div>

      {/* active filter chips */}
      {anyActive ? (
        <div className="activebar">
          {filters.q ? (
            <span className="fchip"><span className="k">Search:</span>{filters.q}<button onClick={() => setFilters((f) => ({ ...f, q: "" }))}><Icon name="x" size={12} /></button></span>
          ) : null}
          {chips.map((c, idx) => (
            <span className="fchip" key={idx}><span className="k">{c.k}:</span>{c.v}
              <button onClick={() => c.key === "time" ? setTime("all") : clearKey(c.key, c.v)}><Icon name="x" size={12} /></button>
            </span>
          ))}
          <button className="clearall" onClick={clearAll}><Icon name="x" size={13} />Clear all</button>
        </div>
      ) : null}
    </div>
  );
}

Object.assign(window, { DispatchFilterBar });
