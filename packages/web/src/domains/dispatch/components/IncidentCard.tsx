import { BellRing, Building2, CarFront, CircleHelp, Flame, HeartPulse, Radio, Siren, Truck, Wrench } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { citiesOfIncident } from '../units';
import {
  CATEGORY_COLOR_CLASS,
  categoryOfIncidentType,
  type DispatchCategory,
} from '../categories';
import {
  type DispatchIncident,
} from '../types';

interface IncidentCardProps {
  incident: DispatchIncident;
  selected: boolean;
  nowMs: number;
  onSelect: (id: number) => void;
}

const CATEGORY_ICON: Record<DispatchCategory, LucideIcon> = {
  Fire: Flame,
  EMS: HeartPulse,
  MVC: CarFront,
  Alarm: BellRing,
  Service: Wrench,
  Other: CircleHelp,
};

function relativeTime(timestamp: string, nowMs: number): string {
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed)) {
    return 'unknown';
  }
  const seconds = Math.max(0, Math.floor((nowMs - parsed) / 1000));
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

export function IncidentCard({ incident, selected, nowMs, onSelect }: IncidentCardProps) {
  const category = categoryOfIncidentType(incident.incident_type);
  const CategoryIcon = CATEGORY_ICON[category];
  const cityLabel = citiesOfIncident(incident.units).join(' · ') || 'Other';

  return (
    <button
      type="button"
      className={[
        'w-full rounded-xl border border-white/10 bg-slate-900/85 p-4 text-left transition hover:bg-slate-800',
        selected ? 'ring-2 ring-safety/70' : '',
      ].join(' ')}
      onClick={() => onSelect(incident.id)}
    >
      <div className="flex items-center gap-2">
        <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-bold ${CATEGORY_COLOR_CLASS[category]}`}>
          <CategoryIcon className="h-3.5 w-3.5" aria-hidden />
          {incident.incident_type}
        </span>
        {incident.special_call ? (
          <span className="inline-flex items-center gap-1 rounded-lg bg-engine px-2 py-1 text-xs font-extrabold text-white">
            <Siren className="h-3.5 w-3.5" aria-hidden />
            SPECIAL
          </span>
        ) : null}
        <span className="ml-auto whitespace-nowrap text-xs text-white/50">{relativeTime(incident.dispatched_at, nowMs)}</span>
      </div>

      <div className="mt-3 text-base font-bold text-white">{incident.address}</div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80">
          <Building2 className="h-3.5 w-3.5 text-white/45" aria-hidden />
          {cityLabel}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-2 py-1 font-mono text-xs font-semibold text-white/80">
          <Radio className="h-3.5 w-3.5 text-white/45" aria-hidden />
          {incident.channel}
        </span>
        {incident.units.slice(0, 4).map((unit) => (
          <span key={unit} className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-2 py-1 text-xs font-semibold text-white/80">
            <Truck className="h-3.5 w-3.5 text-white/45" aria-hidden />
            {unit}
          </span>
        ))}
        {incident.units.length > 4 ? (
          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-xs font-semibold text-white/60">
            +{incident.units.length - 4}
          </span>
        ) : null}
      </div>
    </button>
  );
}
