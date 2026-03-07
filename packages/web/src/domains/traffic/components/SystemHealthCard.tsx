import { useState } from 'react';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthCardProps {
  site: TrafficDecodeSite;
  nowMs: number;
}

function gaugeAccentForStatus(status: string): string {
  switch (status) {
    case 'ok':
      return '#10b981';
    case 'warn':
      return '#f59e0b';
    case 'bad':
      return '#f43f5e';
    default:
      return '#94a3b8';
  }
}

function formatUpdatedAge(updatedAt: string | null, nowMs: number): string {
  if (!updatedAt) {
    return 'Unknown';
  }

  const parsed = new Date(updatedAt).getTime();
  if (Number.isNaN(parsed)) {
    return 'Unknown';
  }

  const deltaSeconds = Math.max(0, Math.floor((nowMs - parsed) / 1000));
  return `${deltaSeconds}s ago`;
}

export function SystemHealthCard({ site, nowMs }: SystemHealthCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const decodeRate = `${site.decode_rate_pct.toFixed(1)}%`;
  const group = site.group || 'Unknown Group';
  const controlChannel = site.control_channel_mhz ? `${site.control_channel_mhz.toFixed(5)} MHz` : 'No control channel';
  const interval = site.interval_s != null ? `${site.interval_s.toFixed(1)}s` : 'Unknown';
  const updated = formatUpdatedAge(site.updated_at, nowMs);
  const decodeRateClamped = Math.max(0, Math.min(100, site.decode_rate_pct));
  const accent = gaugeAccentForStatus(site.status);
  const gaugeBackground = `conic-gradient(${accent} ${decodeRateClamped * 3.6}deg, rgba(255,255,255,0.16) 0deg)`;

  return (
    <article className="card-surface border border-white/15 bg-slate-900/80 p-4 text-slate-100">
      <button
        type="button"
        className="group mx-auto block h-56 w-56 rounded-full border border-white/15 p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-engine]"
        onClick={() => setIsExpanded(true)}
        aria-label={`Open decode details for ${site.sys_name}`}
      >
        <div
          className="relative flex h-full w-full items-center justify-center rounded-full transition-transform group-hover:scale-[1.01]"
          style={{ background: gaugeBackground }}
        >
          <div className="flex h-[76%] w-[76%] flex-col items-center justify-center rounded-full border border-white/20 bg-slate-950/95 px-4 text-center">
            <p className="truncate text-sm font-semibold tracking-wide text-slate-100">{site.sys_name}</p>
            <p className="mt-1 text-3xl font-bold text-slate-100">{decodeRate}</p>
            <p className="mt-1 text-xs uppercase tracking-wider text-slate-300">Decode</p>
          </div>
        </div>
      </button>

      {isExpanded ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 p-4" onClick={() => setIsExpanded(false)}>
          <section
            className="w-full max-w-sm rounded-2xl border border-white/20 bg-slate-900 p-5 text-slate-100 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">{site.sys_name}</h2>
                <p className="text-sm text-slate-300">{group}</p>
              </div>
              <button
                type="button"
                className="rounded-md border border-white/20 px-2 py-1 text-xs text-slate-200 hover:bg-white/10"
                onClick={() => setIsExpanded(false)}
              >
                Close
              </button>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-slate-400">Decode Rate</dt>
                <dd className="font-semibold">{decodeRate}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Status</dt>
                <dd className="font-semibold capitalize">{site.status}</dd>
              </div>
              <div>
                <dt className="text-slate-400">System #</dt>
                <dd className="font-semibold">{site.sys_num}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Interval</dt>
                <dd className="font-semibold">{interval}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-400">Control Channel</dt>
                <dd className="font-semibold">{controlChannel}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-400">Updated</dt>
                <dd className="font-semibold">{updated}</dd>
              </div>
            </dl>
          </section>
        </div>
      ) : null}
    </article>
  );
}
