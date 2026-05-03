import { useState } from 'react';
import { Info, Radio, Search } from 'lucide-react';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthCardProps {
  site: TrafficDecodeSite;
  nowMs: number;
  activeCallsCount: number;
  isSelected: boolean;
  onSelect: () => void;
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

function formatDecodeRateRaw(decodeRatePct: number): string {
  return (decodeRatePct / 2.5).toFixed(1);
}

export function SystemHealthCard({
  site,
  nowMs,
  activeCallsCount,
  isSelected,
  onSelect,
}: SystemHealthCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const decodeRate = `${site.decode_rate_pct.toFixed(1)}%`;
  const decodeRateRaw = formatDecodeRateRaw(site.decode_rate_pct);
  const group = site.group || 'Unknown Group';
  const controlChannel = site.control_channel_mhz ? `${site.control_channel_mhz.toFixed(5)} MHz` : 'No control channel';
  const interval = site.interval_s != null ? `${site.interval_s.toFixed(1)}s` : 'Unknown';
  const updated = formatUpdatedAge(site.updated_at, nowMs);
  const decodeRateClamped = Math.max(0, Math.min(100, site.decode_rate_pct));
  const accent = gaugeAccentForStatus(site.status);
  const gaugeBackground = `conic-gradient(${accent} ${decodeRateClamped * 3.6}deg, rgba(255,255,255,0.16) 0deg)`;

  return (
    <article className="flex flex-col items-center gap-3 p-1 text-slate-100">
      <button
        type="button"
        className={`group mx-auto block h-56 w-56 rounded-full border p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-engine] ${
          isSelected ? 'border-[--color-engine] shadow-[0_0_0_3px_rgba(178,34,34,0.2)]' : 'border-white/15'
        }`}
        onClick={onSelect}
        aria-pressed={isSelected}
        aria-label={`Filter recent calls for ${site.sys_name}`}
      >
        <div
          className="relative flex h-full w-full items-center justify-center rounded-full transition-transform group-hover:scale-[1.01]"
          style={{ background: gaugeBackground }}
        >
          <div className="flex h-[82%] w-[82%] flex-col items-center justify-center rounded-full border border-white/20 bg-slate-950/95 px-4 text-center">
            <p className="truncate text-xl font-extrabold tracking-wide text-slate-100">{site.sys_name}</p>
            <div
              className="tooltip tooltip-bottom mt-2"
              data-tip={`Raw: ${decodeRateRaw} / 40`}
            >
              <p className="inline-flex items-center gap-1 text-lg font-semibold text-slate-200">
                {decodeRate}
                <Info className="h-4 w-4 text-slate-400" aria-hidden />
              </p>
            </div>
            <p className="mt-3 inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200">
              <Radio className="h-3.5 w-3.5" aria-hidden />
              {activeCallsCount} Live
            </p>
          </div>
        </div>
      </button>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold transition ${
            isSelected
              ? 'border-[--color-engine] bg-[--color-engine]/15 text-[--color-engine]'
              : 'border-white/15 bg-white/5 text-slate-200 hover:bg-white/10'
          }`}
          onClick={onSelect}
        >
          <Search className="h-3.5 w-3.5" aria-hidden />
          {isSelected ? 'Showing Filter' : 'Filter Calls'}
        </button>
        <button
          type="button"
          className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-white/10"
          onClick={() => setIsExpanded(true)}
        >
          Details
        </button>
      </div>

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
                <dd className="font-semibold">
                  {decodeRate}
                  <span className="ml-2 text-xs text-slate-400">({decodeRateRaw} / 40 raw)</span>
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Status</dt>
                <dd className="font-semibold capitalize">{site.status}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Active Calls</dt>
                <dd className="font-semibold">{activeCallsCount}</dd>
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
