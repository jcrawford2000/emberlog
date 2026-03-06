import { formatDuration, formatFrequencyMhz, type RecentCall } from '../recentCalls';

interface CallsTableProps {
  calls: RecentCall[];
  rowLimit: number;
  rowLimitOptions: number[];
  onRowLimitChange: (nextValue: number) => void;
}

export function CallsTable({ calls, rowLimit, rowLimitOptions, onRowLimitChange }: CallsTableProps) {
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
      {calls.length === 0 ? (
        <p className="text-sm text-muted">No recent calls yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="table">
            <thead>
              <tr>
                <th>System</th>
                <th>Trunkgroup ID</th>
                <th>Trunkgroup Label</th>
                <th>Frequency</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.call_id}>
                  <td>{call.system}</td>
                  <td className="font-mono text-xs">{call.trunkgroup_id ?? 'n/a'}</td>
                  <td>{call.trunkgroup_label ?? 'n/a'}</td>
                  <td>{formatFrequencyMhz(call.frequency_hz)}</td>
                  <td>{formatDuration(call.duration_seconds, call.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
