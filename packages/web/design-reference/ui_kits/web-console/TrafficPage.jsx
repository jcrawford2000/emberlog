/* Traffic Monitor page — system-health gauges + searchable recent-calls table.
   (Body extracted from the original kit index so Traffic and Dispatch can share one shell.) */
const { useState: useTState, useMemo: useTMemo } = React;

function trafficMatchesSearch(call, search) {
  const q = search.trim().toLowerCase();
  if (!q) return true;
  return [call.sys_name, call.group, call.talkgroup, call.description, call.category, call.tag, String(call.talkgroup_id)]
    .some((v) => (v ?? "").toLowerCase().includes(q));
}

function TrafficPage() {
  const [search, setSearch] = useTState("");
  const [hideEnc, setHideEnc] = useTState(false);
  const [selectedSystem, setSelectedSystem] = useTState(null);
  const [detailSite, setDetailSite] = useTState(null);

  const liveCountBySystem = useTMemo(() => {
    const m = {};
    CALLS.forEach((c) => { if (c.isActive) m[c.sys_name] = (m[c.sys_name] || 0) + 1; });
    return m;
  }, []);
  const activeNow = useTMemo(() => CALLS.filter((c) => c.isActive).length, []);

  const visibleCalls = useTMemo(() => {
    return CALLS
      .filter((c) => (selectedSystem ? c.sys_name === selectedSystem : true))
      .filter((c) => (hideEnc ? !c.encrypted : true))
      .filter((c) => trafficMatchesSearch(c, search))
      .sort((a, b) => {
        if (a.isActive !== b.isActive) return a.isActive ? -1 : 1;
        return new Date(b.lastSeenAt) - new Date(a.lastSeenAt);
      });
  }, [search, hideEnc, selectedSystem]);

  const toggleSystem = (sys) => setSelectedSystem((cur) => (cur === sys ? null : sys));
  const canClear = !!(selectedSystem || search || hideEnc);
  const clearAll = () => { setSelectedSystem(null); setSearch(""); setHideEnc(false); };

  return (
    <React.Fragment>
      <main className="main">
        <PageHead connection="live" lastFetch="3s ago" />
        <FilterBar search={search} onSearch={setSearch} hideEnc={hideEnc} onHideEnc={setHideEnc} onClear={clearAll} canClear={canClear} />
        <SystemGaugeStrip sites={SYSTEMS} liveCountBySystem={liveCountBySystem} selected={selectedSystem} onSelect={toggleSystem} onDetails={setDetailSite} />
        <CallsTable calls={visibleCalls} visibleCount={visibleCalls.length} activeNow={activeNow} selectedSystem={selectedSystem} onSelectSystem={toggleSystem} loading={false} />
        <footer className="legend">
          Talkgroups marked with <Icon name="lock" size={14} /> are encrypted. Calls marked with <Icon name="radio" size={14} /> are the site instance currently being recorded.
        </footer>
      </main>
      <SystemDetailModal site={detailSite} liveCount={detailSite ? (liveCountBySystem[detailSite.sys_name] || 0) : 0} onClose={() => setDetailSite(null)} />
    </React.Fragment>
  );
}
window.TrafficPage = TrafficPage;
