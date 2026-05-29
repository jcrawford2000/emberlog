import {
  ArrowUpRight,
  BellRing,
  Building2,
  CarFront,
  CircleHelp,
  Flame,
  HeartPulse,
  Link,
  MapPin,
  Play,
  Radio,
  Siren,
  Truck,
  Wrench,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useMemo, useState } from 'react';
import { cityOfUnit, citiesOfIncident } from '../units';
import {
  CATEGORY_BG_CLASS,
  CATEGORY_COLOR_CLASS,
  categoryOfIncidentType,
  type DispatchCategory,
} from '../categories';
import {
  type DispatchIncident,
} from '../types';

interface IncidentDetailProps {
  incident: DispatchIncident | null;
  nowMs: number;
}

const CATEGORY_ICON: Record<DispatchCategory, LucideIcon> = {
  Fire: Flame,
  EMS: HeartPulse,
  MVC: CarFront,
  Alarm: BellRing,
  Service: Wrench,
  Other: CircleHelp,
};

function formatClock(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return 'Unknown';
  }
  return parsed.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

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
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
}

function audioName(sourceAudio: string): string {
  if (!sourceAudio) {
    return 'Audio reference unavailable';
  }
  const parts = sourceAudio.split('/');
  return parts[parts.length - 1] || sourceAudio;
}

function Waveform({ category, seed }: { category: DispatchCategory; seed: number }) {
  const bars = useMemo(() => {
    let state = seed * 131 + 7;
    return Array.from({ length: 48 }, (_, index) => {
      state = (state * 9301 + 49297) % 233280;
      const envelope = Math.sin((index / 48) * Math.PI);
      return 18 + Math.round(envelope * (35 + (state / 233280) * 45));
    });
  }, [seed]);

  return (
    <div className="flex h-10 items-center gap-0.5">
      {bars.map((height, index) => (
        <span
          key={index}
          className={`flex-1 rounded-sm ${index < 17 ? CATEGORY_BG_CLASS[category] : 'bg-white/20'}`}
          style={{ height: `${height}%` }}
          aria-hidden
        />
      ))}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-3">
      <dt className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">{label}</dt>
      <dd className="mt-2 flex flex-wrap gap-2 text-sm font-semibold text-white/90">{children}</dd>
    </div>
  );
}

export function IncidentDetail({ incident, nowMs }: IncidentDetailProps) {
  const [raw, setRaw] = useState(false);

  if (!incident) {
    return (
      <section className="flex min-h-80 items-center justify-center rounded-xl border border-white/10 bg-slate-900/85 p-8 text-sm text-white/55">
        Select an incident to see its transcript and details.
      </section>
    );
  }

  const category = categoryOfIncidentType(incident.incident_type);
  const CategoryIcon = CATEGORY_ICON[category];
  const cities = citiesOfIncident(incident.units);
  const transcript = raw ? incident.original_text : incident.transcript;

  return (
    <section className="space-y-4 rounded-xl border border-white/10 bg-slate-900/90 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-bold ${CATEGORY_COLOR_CLASS[category]}`}>
            <CategoryIcon className="h-4 w-4" aria-hidden />
            {category} · {incident.incident_type}
          </span>
          <h2 className="mt-3 text-2xl font-extrabold text-white">{incident.address}</h2>
          <p className="mt-1 text-sm text-white/55">
            Dispatched {formatClock(incident.dispatched_at)} · {relativeTime(incident.dispatched_at, nowMs)} · incident #{incident.id}
          </p>
        </div>
        {incident.special_call ? (
          <span className="inline-flex items-center gap-1 rounded-lg bg-engine px-3 py-1.5 text-xs font-extrabold text-white">
            <Siren className="h-4 w-4" aria-hidden />
            SPECIAL CALL
          </span>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_13rem]">
        <dl className="grid gap-3 sm:grid-cols-2">
          <Field label="City">
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-4 w-4 text-white/45" aria-hidden />
              {cities.join(', ') || 'Other'}
            </span>
          </Field>
          <Field label="Channel">
            <span className="inline-flex items-center gap-1 font-mono">
              <Radio className="h-4 w-4 text-white/45" aria-hidden />
              {incident.channel}
            </span>
          </Field>
          <div className="sm:col-span-2">
            <Field label="Units">
              {incident.units.map((unit) => (
                <span key={unit} className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-xs">
                  <Truck className="h-3.5 w-3.5 text-white/45" aria-hidden />
                  {unit}
                  <span className="font-normal text-white/45">· {cityOfUnit(unit)}</span>
                </span>
              ))}
            </Field>
          </div>
        </dl>
        <div className="relative min-h-36 overflow-hidden rounded-xl border border-white/15 bg-slate-950">
          {/* TODO: Replace placeholder with geocoded tile provider once address geocoding is part of the contract. */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:24px_24px]" />
          <div className="absolute inset-0 grid place-items-center p-4 text-center">
            <div>
              <MapPin className={`mx-auto h-7 w-7 ${CATEGORY_BG_CLASS[category].replace('bg-', 'text-')}`} aria-hidden />
              <p className="mt-2 text-xs font-semibold text-white/70">{incident.address}</p>
            </div>
          </div>
          <span className="absolute left-3 top-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">
            Map · placeholder
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-white/15 bg-slate-950 p-4">
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">Audio · segment</div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            className={`grid h-10 w-10 flex-none place-items-center rounded-full text-white ${CATEGORY_BG_CLASS[category]}`}
            aria-label="Play dispatch audio segment"
          >
            <Play className="ml-0.5 h-5 w-5" aria-hidden />
          </button>
          <div className="min-w-0 flex-1">
            <Waveform category={category} seed={incident.id} />
            <div className="mt-2 flex justify-between gap-3 font-mono text-[11px] text-white/45">
              <span>0:00</span>
              <span className="truncate">{audioName(incident.source_audio)}</span>
              <span>0:08</span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">Transcript</span>
          <span className="inline-flex overflow-hidden rounded-lg border border-white/20">
            <button
              type="button"
              className={`px-3 py-1.5 text-xs font-semibold ${!raw ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10'}`}
              onClick={() => setRaw(false)}
            >
              Cleaned
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 text-xs font-semibold ${raw ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10'}`}
              onClick={() => setRaw(true)}
            >
              Raw STT
            </button>
          </span>
        </div>
        <div className={`rounded-lg border border-white/10 bg-white/5 p-4 text-sm leading-6 text-white/85 ${raw ? 'font-mono text-xs text-white/70' : ''}`}>
          {transcript || 'No transcript available.'}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        {incident.correlation_id ? (
          <a
            className="inline-flex items-center gap-2 rounded-full border border-brass/40 bg-brass/10 px-3 py-1.5 text-sm font-semibold text-yellow-100 hover:bg-brass/15"
            href={`/traffic?correlation_id=${encodeURIComponent(incident.correlation_id)}`}
          >
            <Link className="h-4 w-4" aria-hidden />
            Linked Traffic call
            <span className="font-mono text-xs">{incident.correlation_id}</span>
            <ArrowUpRight className="h-4 w-4" aria-hidden />
          </a>
        ) : (
          <span className="text-sm text-white/45">No linked Traffic call.</span>
        )}
        <span className="font-mono text-xs text-white/45">emberlog-transcriber · {incident.source_audio || 'source pending'}</span>
      </div>
    </section>
  );
}
