import { AnimatePresence, motion } from "framer-motion";
import { AudioLines, Filter, Info, MapPin, Search, Shield } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { fetchIncidents, type IncidentQueryParams } from "./api/emberlogApi";
import { addIncidentDedupeCap } from "./lib/incidentList";
import { openIncidentStream, type LiveState } from "./lib/sse";
import { IncidentSchema, parseIncident, type Incident } from "./types/emberlogTypes";


// --- Types -----------------------------------------------------------------

//type Incident = {
//  id: number;
//  dispatched_at: string; // ISO in UTC
//  incident_type: string;
//  address: string; // freeform street + city
//  units: string[];
//  channel: string; // e.g., "PRWC G" or numeric
//  source_audio?: string; // URL/path
//  transcript?: string;
//};

// --- Utilities -------------------------------------------------------------

function toLocalDisplay(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
  const time = d.toLocaleTimeString(undefined, {
    hour12: true,
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${date} ${time}`;
}

function mapsLink(address: string) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
}

// --- Components ------------------------------------------------------------

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="pill">{children}</span>;
}

function RowExpand({ incident }: { incident: Incident }) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="bg-alt/40 border-t border-border"
    >
      <div className="p-4 grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2 space-y-2">
          <div className="text-sm font-semibold">Transcript</div>
          <div className="text-sm whitespace-pre-wrap leading-relaxed text-body">
            {incident.transcript || "No transcript available."}
          </div>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-semibold">Audio</div>
          {incident.source_audio ? (
            <audio controls preload="none" className="w-full">
              <source src={incident.source_audio} />
            </audio>
          ) : (
            <div className="text-sm text-muted">No audio file.</div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function EmberlogApp() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [unitFilter, setUnitFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [fromFilter, setFromFilter] = useState<string | null>(null);
  const [toFilter, setToFilter] = useState<string | null>(null);
  const [live, setLive] = useState<LiveState>("connecting");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
  }, [typeFilter, query, unitFilter, channelFilter, fromFilter, toFilter]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: IncidentQueryParams = {
          incident_type: typeFilter === "ALL" ? undefined : typeFilter,
          address_search: query.trim() || undefined,
          channel: channelFilter.trim() || undefined,
          units: unitFilter.trim() ? [unitFilter.trim()] : undefined,
          from_dispatched_at: fromFilter
            ? new Date(fromFilter).toISOString()
            : undefined,
          to_dispatched_at: toFilter ? new Date(toFilter).toISOString() : undefined,
          page,
          page_size: pageSize,
        };
        const response = await fetchIncidents(params);
        if (!active) return;
        setIncidents(response.items);
        setTotal(response.total ?? null);
      } catch (e) {
        if (!active) return;
        console.error("Failed to fetch incidents", e);
        setError("Failed to load incidents. Please try again.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [typeFilter, query, unitFilter, channelFilter, fromFilter, toFilter, page, pageSize]);

  const incidentTypes = useMemo(() => {
    const s = new Set(incidents.map((r) => r.incident_type));
    return ["ALL", ...Array.from(s).sort()];
  }, [incidents]);

  const totalPages = useMemo(() => {
    if (!total) return null;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [pageSize, total]);

  useEffect(() => {
    const stop = openIncidentStream({
      onStatus: setLive,
      onIncident: (json) => {
        let incoming: Incident | null = null;
        try {
          const parsed = JSON.parse(json);
          const validated = IncidentSchema.safeParse(parsed);
          incoming = validated.success
            ? {
                ...validated.data,
                source_audio: validated.data.source_audio ?? undefined,
                transcript: validated.data.transcript ?? undefined,
              }
            : null;
        } catch (err) {
          incoming = parseIncident(json);
        }

        if (!incoming) {
          console.warn("Bad incident JSON from SSE:", json);
          return;
        }

        const matchesType =
          typeFilter === "ALL" || incoming.incident_type === typeFilter;
        const matchesAddress =
          !query.trim() ||
          (incoming.address ?? "").toLowerCase().includes(query.trim().toLowerCase());
        const matchesUnit =
          !unitFilter.trim() ||
          (incoming.units ?? []).some((u) =>
            u.toLowerCase().includes(unitFilter.trim().toLowerCase()),
          );
        const matchesChannel =
          !channelFilter.trim() ||
          (incoming.channel ?? "")
            .toLowerCase()
            .includes(channelFilter.trim().toLowerCase());

        let matchesDate = true;
        const d = new Date(incoming.dispatched_at);

        if (fromFilter && d < new Date(fromFilter)) matchesDate = false;
        if (toFilter && d > new Date(toFilter)) matchesDate = false;

        if (
          matchesType &&
          matchesAddress &&
          matchesUnit &&
          matchesChannel &&
          matchesDate &&
          page === 1
        ) {
          setIncidents((prev) => addIncidentDedupeCap(incoming, prev, pageSize));
        }
      },
    });
    return stop;
  }, [typeFilter, query, unitFilter, channelFilter, fromFilter, toFilter, page, pageSize]);



  const filtered = useMemo(() => {
    return typeFilter === "ALL"
      ? incidents
      : incidents.filter((r) => r.incident_type === typeFilter);
  }, [incidents, typeFilter]);

  return (
    <div className="min-h-screen bg-surface text-primary-text">
      {/* Top Banner */}
      <header className="sticky top-0 z-20 backdrop-blur bg-engine ">
        <div className="mx-auto max-w-7xl px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="h-9 w-15 rounded-2xl text-white grid place-items-center shadow">
                <AudioLines className="h-10 w-15 bg-safety rounded-2xl" />
              </div>
              <div className="font-bold tracking-wide text-2xl text-white">Emberlog</div>
            </div>
            <div className="flex-1" />
            <div className="hidden md:flex items-center gap-2 text-xs text-white/80">
              <Shield className="h-4 w-4" />
              <span>Status: {live}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-4 py-6 space-y-6">
        {/* Search + Filters Row */}
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <div className="relative">
              <Search
                aria-hidden
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-white/70"
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search address / location"
                className="input-ember w-full px-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <div className="inline-flex items-center gap-2 rounded-xl bg-white/10 border border-white/20 px-3 py-2">
                <Filter className="h-4 w-4" />
                <select
                  className="bg-transparent focus:outline-none"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  {incidentTypes.map((t) => (
                    <option key={t} value={t} className="text-body">
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <input
              value={unitFilter}
              onChange={(e) => setUnitFilter(e.target.value)}
              placeholder="Unit (e.g., E605)"
              className="input-ember w-full"
            />
            <input
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              placeholder="Channel"
              className="input-ember w-full"
            />
            <label className="flex flex-col gap-1 text-sm text-muted">
              <span>From</span>
              <input
                type="datetime-local"
                value={fromFilter ?? ""}
                onChange={(e) => setFromFilter(e.target.value || null)}
                className="input-ember"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted">
              <span>To</span>
              <input
                type="datetime-local"
                value={toFilter ?? ""}
                onChange={(e) => setToFilter(e.target.value || null)}
                className="input-ember"
              />
            </label>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-400/40 bg-red-900/30 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        )}

        {/* Results Card */}
        <div className="card-surface overflow-hidden">
          <div className="border-b border-border bg-alt/40 px-4 py-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="font-semibold text-body">Latest Dispatches</div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-sm text-muted">
                {loading
                  ? "Loading…"
                  : `Showing ${filtered.length}${total ? ` of ${total}` : ""} incidents`}
              </div>
              <div className="flex items-center gap-2 text-sm text-muted">
                <button
                  className="inline-flex items-center gap-1 rounded-lg border border-white/20 px-2 py-1 text-xs disabled:opacity-50"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1 || loading}
                >
                  Previous
                </button>
                <span>
                  Page {page}
                  {total ? ` / ${totalPages}` : ""}
                </span>
                <button
                  className="inline-flex items-center gap-1 rounded-lg border border-white/20 px-2 py-1 text-xs disabled:opacity-50"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!!(totalPages && page >= totalPages) || loading}
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-black/5">
                <tr>
                  <th className="text-left px-4 py-2">Date/Time</th>
                  <th className="text-left px-4 py-2">Type</th>
                  <th className="text-left px-4 py-2">Address</th>
                  <th className="text-left px-4 py-2">Channel</th>
                  <th className="text-left px-4 py-2">Units</th>
                  <th className="text-right px-4 py-2">Info</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inc) => {
                  const isOpen = !!expanded[inc.id];
                  return (
                    <React.Fragment key={inc.id}>
                      <tr className="hover:bg-black/5">
                        <td className="px-4 py-2 align-top whitespace-nowrap">
                          {toLocalDisplay(inc.dispatched_at)}
                        </td>
                        <td className="px-4 py-2 align-top font-medium text-[--color-engine]">
                          {inc.incident_type}
                        </td>
                        <td className="px-4 py-2 align-top">
                          <a
                            href={mapsLink(inc.address)}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 underline decoration-dotted underline-offset-2 hover:decoration-solid"
                          >
                            <MapPin className="h-4 w-4" /> {inc.address}
                          </a>
                        </td>
                        <td className="px-4 py-2 align-top">{inc.channel}</td>
                        <td className="px-4 py-2 align-top">
                          <div className="flex flex-wrap gap-1">
                            {inc.units.map((u) => (
                              <Pill key={u}>{u}</Pill>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-2 align-top text-right">
                          <button
                            onClick={() =>
                              setExpanded((s) => ({ ...s, [inc.id]: !s[inc.id] }))
                            }
                            className="inline-flex items-center gap-1 rounded-lg border border-black/20 px-2 py-1 hover:bg-[--color-brass]/20"
                            aria-expanded={isOpen}
                            aria-controls={`expand-${inc.id}`}
                          >
                            <Info className="h-4 w-4" />
                            <span className="hidden sm:inline">Details</span>
                          </button>
                        </td>
                      </tr>
                      <tr>
                        <td colSpan={6} className="p-0">
                          <AnimatePresence initial={false}>
                            {isOpen && (
                              <RowExpand incident={inc} key={`exp-${inc.id}`} />
                            )}
                          </AnimatePresence>
                        </td>
                      </tr>
                    </React.Fragment>
                  );
                })}

                {filtered.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-sm text-white/60">
                      No incidents match your search. Try a broader query.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <footer className="text-xs text-white/70 text-center py-6">
          Phoenix area data. Emberlog theme colors applied.
        </footer>
      </main>
    </div>
  );
}
