import type { TrafficDecodeSite } from '../types';

interface SystemHealthCardProps {
  site: TrafficDecodeSite;
  nowMs: number;
}

function badgeClassForStatus(status: string): string {
  switch (status) {
    case 'ok':
      return 'badge-success';
    case 'warn':
      return 'badge-warning';
    case 'bad':
      return 'badge-error';
    default:
      return 'badge-neutral';
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
  const decodeRate = `${site.decode_rate_pct.toFixed(1)}%`;

  return (
    <article className="card-surface p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">{site.group || 'Unknown Group'}</p>
          <h2 className="text-lg font-semibold">{site.sys_name}</h2>
        </div>
        <span className={`badge ${badgeClassForStatus(site.status)}`}>{site.status.toUpperCase()}</span>
      </div>

      <div className="mb-4 flex items-end justify-between gap-2">
        <div>
          <p className="text-xs text-muted">Decode rate</p>
          <p className="text-2xl font-bold text-body">{decodeRate}</p>
        </div>
        <div className="text-right text-xs text-muted">
          <p>System #{site.sys_num}</p>
          {site.control_channel_mhz ? <p>{site.control_channel_mhz.toFixed(5)} MHz</p> : <p>No control channel</p>}
        </div>
      </div>

      <div className="text-xs text-muted">
        <p>Updated {formatUpdatedAge(site.updated_at, nowMs)}</p>
      </div>
    </article>
  );
}
