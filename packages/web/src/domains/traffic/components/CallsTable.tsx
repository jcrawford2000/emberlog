import { formatDuration, formatFrequencyMhz, type RecentCall } from '../recentCalls';

interface CallsTableProps {
  calls: RecentCall[];
  rowLimit: number;
  rowLimitOptions: number[];
  onRowLimitChange: (nextValue: number) => void;
}

export function CallsTable({ calls, rowLimit, rowLimitOptions, onRowLimitChange }: CallsTableProps) {
  const formatDateTime = (timestamp: string): string => {
    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) {
      return 'Unknown';
    }
    return parsed.toLocaleString();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-2 text-sm">
        <label htmlFor="recent-calls-limit" className="text-white/75">
          Show
        </label>
        <select
          id="recent-calls-limit"
          className="select select-sm select-bordered"
          value={rowLimit}
          onChange={(event) => onRowLimitChange(Number(event.target.value))}
        >
          {rowLimitOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="table">
          <thead>
            <tr>
              <th>Date/Time</th>
              <th>System</th>
              <th>Trunkgroup ID</th>
              <th>Trunkgroup Label</th>
              <th>Frequency</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-sm text-muted">
                  No recent calls yet.
                </td>
              </tr>
            ) : (
              calls.map((call) => (
                <tr key={call.call_id}>
                  <td className="whitespace-nowrap">{formatDateTime(call.latest_event_at)}</td>
                  <td>{call.system}</td>
                  <td className="font-mono text-xs">{call.trunkgroup_id ?? 'n/a'}</td>
                  <td>{call.trunkgroup_label ?? 'n/a'}</td>
                  <td>{formatFrequencyMhz(call.frequency_hz)}</td>
                  <td>
                    {call.status === 'live' ? (
                      <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-300" aria-hidden />
                        LIVE
                      </span>
                    ) : (
                      formatDuration(call.duration_seconds, call.status)
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
