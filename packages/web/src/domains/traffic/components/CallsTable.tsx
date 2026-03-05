import { useMemo, useState } from 'react';
import type { LiveCall } from '../types';

interface CallsTableProps {
  calls: LiveCall[];
}

function formatTimestamp(value: string): string {
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) {
    return 'Unknown';
  }
  return time.toLocaleString();
}

export function CallsTable({ calls }: CallsTableProps) {
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  const selectedCall = useMemo(() => {
    if (!selectedCallId) {
      return null;
    }
    return calls.find((call) => call.callId === selectedCallId) ?? null;
  }, [calls, selectedCallId]);

  if (calls.length === 0) {
    return <p className="text-sm text-muted">No active calls right now.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="table">
          <thead>
            <tr>
              <th>System</th>
              <th>Site</th>
              <th>Call ID</th>
              <th>Frequency</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <tr
                key={call.callId}
                className="cursor-pointer hover:bg-white/5"
                onClick={() => setSelectedCallId(call.callId)}
              >
                <td>{call.system}</td>
                <td>{call.site}</td>
                <td className="font-mono text-xs">{call.callId}</td>
                <td>{typeof call.frequency === 'number' ? call.frequency.toFixed(5) : 'n/a'}</td>
                <td>{formatTimestamp(call.startedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedCall ? (
        <section className="rounded-xl border border-white/20 bg-white/5 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Call Details</h3>
            <button className="btn btn-xs" onClick={() => setSelectedCallId(null)}>
              Close
            </button>
          </div>
          <pre className="max-h-64 overflow-auto rounded-lg bg-black/30 p-3 text-xs text-white/80">
            {JSON.stringify(selectedCall.rawPayload, null, 2)}
          </pre>
        </section>
      ) : null}
    </div>
  );
}
