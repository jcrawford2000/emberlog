import type { ConnectionStatus } from '../../../core/realtime/types';

interface TrafficHeaderProps {
  connectionStatus: ConnectionStatus;
  isPollingFallback: boolean;
  pollIntervalMs: number;
  lastFetchedAt: number | null;
}

function formatAge(ms: number): string {
  if (ms < 1000) {
    return 'just now';
  }

  const seconds = Math.floor(ms / 1000);
  return `${seconds}s ago`;
}

export function TrafficHeader({
  connectionStatus,
  isPollingFallback,
  pollIntervalMs,
  lastFetchedAt,
}: TrafficHeaderProps) {
  const statusConfig =
    connectionStatus === 'live'
      ? { label: 'Live', dotClass: 'bg-lime-300' }
      : connectionStatus === 'reconnecting'
        ? { label: 'Reconnecting', dotClass: 'bg-amber-300' }
        : connectionStatus === 'connecting'
          ? { label: 'Connecting', dotClass: 'bg-sky-300' }
          : { label: 'Offline', dotClass: 'bg-rose-300' };

  const pollIntervalSeconds = Math.floor(pollIntervalMs / 1000);
  const fetchedAge = lastFetchedAt ? formatAge(Date.now() - lastFetchedAt) : 'waiting';

  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">Traffic Monitor</h1>
        <p className="text-sm text-white/70">Snapshot from /api/v1/traffic/summary + live updates from /api/v1/sse</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-sm">
          <span className={`h-2 w-2 rounded-full ${statusConfig.dotClass}`} aria-hidden />
          <span>
            {isPollingFallback ? `Polling fallback (${pollIntervalSeconds}s)` : statusConfig.label}
          </span>
        </div>
        <span className="text-xs text-white/70">Last fetch: {fetchedAge}</span>
      </div>
    </div>
  );
}
