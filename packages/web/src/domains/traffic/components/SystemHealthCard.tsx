import { useId, useState } from 'react';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthCardProps {
  site: TrafficDecodeSite;
  nowMs: number;
}

function cardClassForStatus(status: string): string {
  switch (status) {
    case 'ok':
      return '!border-emerald-500/60 !bg-emerald-500/18 hover:!bg-emerald-500/24';
    case 'warn':
      return '!border-amber-500/65 !bg-amber-400/24 hover:!bg-amber-400/30';
    case 'bad':
      return '!border-rose-500/70 !bg-rose-500/22 hover:!bg-rose-500/30';
    default:
      return '!border-slate-500/55 !bg-slate-400/20 hover:!bg-slate-400/28';
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
  const detailsId = useId();
  const decodeRate = `${site.decode_rate_pct.toFixed(1)}%`;
  const group = site.group || 'Unknown Group';
  const controlChannel = site.control_channel_mhz ? `${site.control_channel_mhz.toFixed(5)} MHz` : 'No control channel';
  const toggleLabel = isExpanded ? 'Collapse details' : 'Expand details';

  return (
    <article className={`card-surface border p-0 text-body transition-colors ${cardClassForStatus(site.status)}`}>
      <button
        type="button"
        className="w-full p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-engine]"
        onClick={() => setIsExpanded((current) => !current)}
        aria-expanded={isExpanded}
        aria-controls={detailsId}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-lg font-semibold">{site.sys_name}</h2>
          <span className="text-sm text-body/70" aria-hidden>
            {isExpanded ? '▾' : '▸'}
          </span>
        </div>

        <div className="mt-2">
          <p className="text-xs uppercase tracking-wide text-body/70">Decode rate</p>
          <p className="text-3xl font-bold leading-tight">{decodeRate}</p>
        </div>

        <span className="sr-only">
          {site.status} status. {toggleLabel}.
        </span>

        {isExpanded ? (
          <div id={detailsId} className="mt-4 border-t border-black/10 pt-3 text-xs text-body/80">
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <div>
                <dt className="uppercase tracking-wide text-body/60">Group</dt>
                <dd className="text-sm font-medium text-body">{group}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-body/60">Frequency</dt>
                <dd className="text-sm font-medium text-body">{controlChannel}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-body/60">System</dt>
                <dd className="text-sm font-medium text-body">#{site.sys_num}</dd>
              </div>
            </dl>
            <p className="mt-2 text-body/65">Updated {formatUpdatedAge(site.updated_at, nowMs)}</p>
          </div>
        ) : null}
      </button>
    </article>
  );
}
