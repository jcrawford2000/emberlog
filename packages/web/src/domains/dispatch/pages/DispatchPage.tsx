import { useEffect, useMemo, useState } from 'react';
import { DispatchFilters } from '../components/DispatchFilters';
import { IncidentDetail } from '../components/IncidentDetail';
import { IncidentFeed } from '../components/IncidentFeed';
import { useDispatchIncidents } from '../hooks/useDispatchIncidents';
import { citiesOfIncident } from '../units';
import { categoryOfIncidentType, type DispatchCategory } from '../categories';
import {
  type DispatchFiltersState,
  type DispatchIncident,
} from '../types';

const DEFAULT_FILTERS: DispatchFiltersState = {
  q: '',
  time: 'all',
  cities: [],
  units: [],
  types: [],
  categories: [],
  channels: [],
};

function formatAge(ms: number): string {
  if (ms < 1000) {
    return 'just now';
  }
  return `${Math.floor(ms / 1000)}s ago`;
}

function withinTimeWindow(incident: DispatchIncident, filters: DispatchFiltersState, nowMs: number): boolean {
  if (filters.time === 'all') {
    return true;
  }

  const dispatchedMs = Date.parse(incident.dispatched_at);
  if (!Number.isFinite(dispatchedMs)) {
    return false;
  }

  const ageSeconds = (nowMs - dispatchedMs) / 1000;
  if (filters.time === 'live') {
    return ageSeconds <= 120;
  }
  if (filters.time === '1h') {
    return ageSeconds <= 3600;
  }
  return ageSeconds <= 14400;
}

function matchesQuery(incident: DispatchIncident, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  const haystack = [
    incident.address,
    incident.incident_type,
    incident.channel,
    incident.transcript,
    incident.original_text,
    incident.units.join(' '),
    citiesOfIncident(incident.units).join(' '),
  ].join(' ').toLowerCase();

  return haystack.includes(normalized);
}

function passesFilters(incident: DispatchIncident, filters: DispatchFiltersState, nowMs: number): boolean {
  if (!matchesQuery(incident, filters.q)) {
    return false;
  }
  if (!withinTimeWindow(incident, filters, nowMs)) {
    return false;
  }

  const incidentCities = citiesOfIncident(incident.units);
  if (filters.cities.length > 0 && !incidentCities.some((city) => filters.cities.includes(city))) {
    return false;
  }
  if (filters.units.length > 0 && !incident.units.some((unit) => filters.units.includes(unit))) {
    return false;
  }
  if (filters.types.length > 0 && !filters.types.includes(incident.incident_type)) {
    return false;
  }
  if (
    filters.categories.length > 0 &&
    !filters.categories.includes(categoryOfIncidentType(incident.incident_type))
  ) {
    return false;
  }
  if (filters.channels.length > 0 && !filters.channels.includes(incident.channel)) {
    return false;
  }
  return true;
}

function topCategory(incidents: DispatchIncident[]): { category: DispatchCategory; count: number } | null {
  const counts = new Map<DispatchCategory, number>();
  for (const incident of incidents) {
    const category = categoryOfIncidentType(incident.incident_type);
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }

  const sorted = [...counts.entries()].sort((left, right) => right[1] - left[1]);
  const first = sorted[0];
  return first ? { category: first[0], count: first[1] } : null;
}

function Header({
  connectionStatus,
  isPollingFallback,
  pollIntervalMs,
  lastFetchedAt,
}: {
  connectionStatus: 'connecting' | 'live' | 'reconnecting' | 'offline';
  isPollingFallback: boolean;
  pollIntervalMs: number;
  lastFetchedAt: number | null;
}) {
  const statusConfig =
    connectionStatus === 'live'
      ? { label: 'Live', dotClass: 'bg-lime-300' }
      : connectionStatus === 'reconnecting'
        ? { label: 'Reconnecting', dotClass: 'bg-amber-300' }
        : connectionStatus === 'connecting'
          ? { label: 'Connecting', dotClass: 'bg-sky-300' }
          : { label: 'Offline', dotClass: 'bg-rose-300' };
  const fetchedAge = lastFetchedAt ? formatAge(Date.now() - lastFetchedAt) : 'waiting';

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">Dispatch Intelligence</h1>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-sm">
          <span className={`h-2 w-2 rounded-full ${statusConfig.dotClass}`} aria-hidden />
          <span>{isPollingFallback ? `Polling fallback (${Math.floor(pollIntervalMs / 1000)}s)` : statusConfig.label}</span>
        </div>
        <span className="text-xs text-white/70">Last fetch: {fetchedAge}</span>
      </div>
    </div>
  );
}

function KpiStrip({ incidents, nowMs }: { incidents: DispatchIncident[]; nowMs: number }) {
  const oneHourAgo = nowMs - 3600 * 1000;
  const fiveMinutesAgo = nowMs - 300 * 1000;
  const incidentsLastHour = incidents.filter((incident) => Date.parse(incident.dispatched_at) >= oneHourAgo);
  const incidentsLastFive = incidents.filter((incident) => Date.parse(incident.dispatched_at) >= fiveMinutesAgo);
  const activeUnits = new Set(incidentsLastHour.flatMap((incident) => incident.units));
  const activeCities = new Set(incidentsLastHour.flatMap((incident) => citiesOfIncident(incident.units)));
  const specialCalls = incidentsLastHour.filter((incident) => incident.special_call).length;
  const top = topCategory(incidentsLastHour);

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div className="card-surface p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Incidents · 1h</div>
        <div className="mt-2 text-3xl font-extrabold">{incidentsLastHour.length}</div>
        <div className="mt-1 text-sm text-muted">{incidentsLastFive.length} in last 5 min</div>
      </div>
      <div className="card-surface p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Active Units</div>
        <div className="mt-2 text-3xl font-extrabold">{activeUnits.size}</div>
        <div className="mt-1 text-sm text-muted">{activeCities.size} cities</div>
      </div>
      <div className="card-surface p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Special Calls</div>
        <div className="mt-2 text-3xl font-extrabold text-engine">{specialCalls}</div>
        <div className="mt-1 text-sm text-muted">last 1h</div>
      </div>
      <div className="card-surface p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Top Category</div>
        <div className="mt-3 text-lg font-extrabold">{top ? `${top.category} · ${top.count}` : 'n/a'}</div>
        <div className="mt-2 text-sm text-muted">filtered from current snapshot</div>
      </div>
    </div>
  );
}

function LoadingPanels() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(22rem,28rem)_1fr]">
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-white/10 bg-slate-900/85 p-4">
            <div className="skeleton mb-3 h-6 w-36" />
            <div className="skeleton mb-3 h-5 w-52" />
            <div className="skeleton h-4 w-44" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-white/10 bg-slate-900/85 p-5">
        <div className="skeleton mb-4 h-6 w-48" />
        <div className="skeleton mb-4 h-10 w-80" />
        <div className="skeleton h-48 w-full" />
      </div>
    </div>
  );
}

export function DispatchPage() {
  const {
    incidents,
    loading,
    error,
    refreshSnapshot,
    lastFetchedAt,
    connectionStatus,
    isPollingFallback,
    pollIntervalMs,
  } = useDispatchIncidents();
  const [filters, setFilters] = useState<DispatchFiltersState>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const filteredIncidents = useMemo(
    () => incidents.filter((incident) => passesFilters(incident, filters, nowMs)),
    [filters, incidents, nowMs]
  );

  const selectedIncident = useMemo(
    () => filteredIncidents.find((incident) => incident.id === selectedId) ?? filteredIncidents[0] ?? null,
    [filteredIncidents, selectedId]
  );

  useEffect(() => {
    if (selectedIncident && selectedIncident.id !== selectedId) {
      setSelectedId(selectedIncident.id);
    }
  }, [selectedId, selectedIncident]);

  return (
    <div className="space-y-6">
      <Header
        connectionStatus={connectionStatus}
        isPollingFallback={isPollingFallback}
        pollIntervalMs={pollIntervalMs}
        lastFetchedAt={lastFetchedAt}
      />

      <KpiStrip incidents={incidents} nowMs={nowMs} />

      <DispatchFilters
        filters={filters}
        incidents={incidents}
        resultCount={filteredIncidents.length}
        onChange={setFilters}
      />

      {error ? (
        <div className="alert alert-error flex items-center justify-between">
          <span>{error}</span>
          <button className="btn btn-sm" onClick={() => void refreshSnapshot()}>
            Retry
          </button>
        </div>
      ) : null}

      {loading && incidents.length === 0 ? (
        <LoadingPanels />
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(22rem,28rem)_1fr]">
          <div className="lg:sticky lg:top-24 lg:h-[calc(100vh-7rem)] lg:min-h-[32rem]">
            <IncidentFeed
              incidents={filteredIncidents}
              selectedId={selectedIncident?.id ?? null}
              nowMs={nowMs}
              onSelect={setSelectedId}
            />
          </div>
          <div className="lg:sticky lg:top-24">
            <IncidentDetail incident={selectedIncident} nowMs={nowMs} />
          </div>
        </div>
      )}
    </div>
  );
}
