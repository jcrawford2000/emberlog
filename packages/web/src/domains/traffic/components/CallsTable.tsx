import { Lock, Radio } from 'lucide-react';
import { formatDuration, formatFrequencyMhz, type RecentCall } from '../recentCalls';

interface CallsTableProps {
  calls: RecentCall[];
  selectedSystem: string | null;
  rowLimit: number;
  rowLimitOptions: number[];
  onRowLimitChange: (nextValue: number) => void;
}

export function CallsTable({
  calls,
  selectedSystem,
  rowLimit,
  rowLimitOptions,
  onRowLimitChange,
}: CallsTableProps) {
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
          className="select select-sm border-white/30 bg-slate-900 text-white"
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
        <table className="table bg-slate-900/90 text-slate-100">
          <thead className="bg-slate-800 text-slate-100">
            <tr>
              <th className="text-slate-100">Date/Time</th>
              <th className="text-slate-100">System</th>
              <th className="text-slate-100">Trunkgroup ID</th>
              <th className="text-slate-100">Trunkgroup Label</th>
              <th className="text-slate-100">Frequency</th>
              <th className="text-slate-100">Flags</th>
              <th className="text-slate-100">Duration</th>
            </tr>
          </thead>
          <tbody className="text-slate-100">
            {calls.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-6 text-center text-sm text-slate-300">
                  {selectedSystem ? `No recent calls for ${selectedSystem} yet.` : 'No recent calls yet.'}
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
                    <div className="flex flex-wrap gap-2">
                      {call.encrypted ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-xs font-semibold text-amber-200"
                          title="Encrypted talkgroup"
                        >
                          <Lock className="h-3.5 w-3.5" aria-hidden />
                          ENC
                        </span>
                      ) : null}
                      {call.is_recording ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-full border border-rose-400/40 bg-rose-500/15 px-2 py-0.5 text-xs font-semibold text-rose-200"
                          title="This call is recording"
                        >
                          <Radio className="h-3.5 w-3.5" aria-hidden />
                          REC
                        </span>
                      ) : null}
                      {!call.encrypted && !call.is_recording ? <span className="text-slate-400">-</span> : null}
                    </div>
                  </td>
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
