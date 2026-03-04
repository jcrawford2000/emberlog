import { useEffect, useState } from 'react';
import { SystemHealthStrip } from '../components/SystemHealthStrip';
import { TrafficHeader } from '../components/TrafficHeader';
import { useTrafficSummary } from '../hooks/useTrafficSummary';

function LoadingCards() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Loading decode rates">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="card-surface p-4">
          <div className="skeleton mb-2 h-4 w-24" />
          <div className="skeleton mb-4 h-6 w-36" />
          <div className="skeleton mb-2 h-10 w-28" />
          <div className="skeleton h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

export function TrafficPage() {
  const { data, loading, error, refresh, lastFetchedAt, pollIntervalMs } = useTrafficSummary();
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="space-y-6">
      <TrafficHeader pollIntervalMs={pollIntervalMs} lastFetchedAt={lastFetchedAt} />

      {loading && !data ? (
        <LoadingCards />
      ) : null}

      {error ? (
        <div className="alert alert-error flex items-center justify-between">
          <span>{error}</span>
          <button className="btn btn-sm" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : null}

      {data && data.decode_sites.length > 0 ? (
        <SystemHealthStrip sites={data.decode_sites} nowMs={nowMs} />
      ) : null}

      {data && data.decode_sites.length === 0 && !error ? (
        <div className="rounded-xl border border-dashed border-white/20 bg-white/5 p-6 text-sm text-white/75">
          No systems are currently reporting decode rates.
        </div>
      ) : null}

      <section className="card-surface p-6">
        <h2 className="mb-2 text-lg font-semibold">Live Calls</h2>
        <p className="text-sm text-muted">Live calls will appear when SSE is implemented.</p>
      </section>
    </div>
  );
}
