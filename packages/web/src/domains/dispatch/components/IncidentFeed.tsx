import type { DispatchIncident } from '../types';
import { IncidentCard } from './IncidentCard';

interface IncidentFeedProps {
  incidents: DispatchIncident[];
  selectedId: number | null;
  nowMs: number;
  onSelect: (id: number) => void;
}

export function IncidentFeed({ incidents, selectedId, nowMs, onSelect }: IncidentFeedProps) {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-3 flex-none text-xs font-semibold uppercase tracking-[0.18em] text-white/45">
        Live Feed · {incidents.length} shown
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain pr-2">
        {incidents.length > 0 ? (
          incidents.map((incident) => (
            <IncidentCard
              key={incident.id}
              incident={incident}
              selected={incident.id === selectedId}
              nowMs={nowMs}
              onSelect={onSelect}
            />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-white/20 p-8 text-center text-sm text-white/55">
            No incidents match these filters.
          </div>
        )}
      </div>
    </section>
  );
}
