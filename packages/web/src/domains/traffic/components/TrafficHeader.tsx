interface TrafficHeaderProps {
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

export function TrafficHeader({ pollIntervalMs, lastFetchedAt }: TrafficHeaderProps) {
  const pollIntervalSeconds = Math.floor(pollIntervalMs / 1000);
  const fetchedAge = lastFetchedAt ? formatAge(Date.now() - lastFetchedAt) : 'waiting';

  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">Traffic Monitor</h1>
        <p className="text-sm text-white/70">Decode health snapshot from /api/v1/traffic/summary</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-sm">
          <span className="h-2 w-2 animate-pulse rounded-full bg-lime-300" aria-hidden />
          <span>Polling ({pollIntervalSeconds}s)</span>
        </div>
        <span className="text-xs text-white/70">Last fetch: {fetchedAge}</span>
      </div>
    </div>
  );
}
