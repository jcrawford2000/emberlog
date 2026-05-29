import type { EventEnvelope } from '../../core/realtime/types';
import {
  DispatchIncidentSchema,
  type DispatchIncident,
  type DispatchIncidentList,
} from './types';

const INCIDENT_LIMIT = 200;

function parseTimestampMs(timestamp: string): number {
  const parsed = Date.parse(timestamp);
  return Number.isFinite(parsed) ? parsed : 0;
}

function compareIncidents(left: DispatchIncident, right: DispatchIncident): number {
  const byDispatchedAt = parseTimestampMs(right.dispatched_at) - parseTimestampMs(left.dispatched_at);
  if (byDispatchedAt !== 0) {
    return byDispatchedAt;
  }
  return right.id - left.id;
}

export function normalizeIncident(input: unknown): DispatchIncident | null {
  if (typeof input !== 'object' || input === null) {
    return null;
  }

  const record = input as Record<string, unknown>;
  const normalized = {
    id: record.id,
    dispatched_at: record.dispatched_at,
    special_call: record.special_call ?? false,
    units: Array.isArray(record.units) ? record.units : [],
    channel: typeof record.channel === 'string' ? record.channel : 'Unknown',
    incident_type: typeof record.incident_type === 'string' ? record.incident_type : 'Unknown',
    address: typeof record.address === 'string' ? record.address : 'Unknown address',
    source_audio: typeof record.source_audio === 'string' ? record.source_audio : '',
    original_text: typeof record.original_text === 'string' ? record.original_text : '',
    transcript: typeof record.transcript === 'string' ? record.transcript : '',
    parsed:
      typeof record.parsed === 'object' && record.parsed !== null && !Array.isArray(record.parsed)
        ? record.parsed
        : {},
    created_at: typeof record.created_at === 'string' ? record.created_at : record.dispatched_at,
    correlation_id: typeof record.correlation_id === 'string' ? record.correlation_id : undefined,
  };

  const parsed = DispatchIncidentSchema.safeParse(normalized);
  if (parsed.success) {
    return parsed.data;
  }
  return null;
}

export function normalizeIncidentList(input: unknown): DispatchIncidentList | null {
  const result = DispatchIncidentSchema.array().safeParse(input);
  if (result.success) {
    return {
      items: result.data,
      total: result.data.length,
      page: 1,
      page_size: result.data.length,
    };
  }
  return null;
}

export function sortRecentIncidents(incidents: Iterable<DispatchIncident>): DispatchIncident[] {
  return [...incidents].sort(compareIncidents);
}

export function mapSnapshotIncidents(incidents: DispatchIncident[]): Map<number, DispatchIncident> {
  const sorted = sortRecentIncidents(incidents).slice(0, INCIDENT_LIMIT);
  return new Map(sorted.map((incident) => [incident.id, incident]));
}

export function mergeIncidentEvent(
  current: Map<number, DispatchIncident>,
  event: EventEnvelope
): Map<number, DispatchIncident> {
  if (
    event.event_type !== 'dispatch.incident.created' &&
    event.event_type !== 'dispatch.incident.updated'
  ) {
    return current;
  }

  const incident = normalizeIncident({
    ...(typeof event.payload === 'object' && event.payload !== null ? event.payload : {}),
    correlation_id:
      typeof event.correlation_id === 'string'
        ? event.correlation_id
        : typeof (event.payload as { correlation_id?: unknown }).correlation_id === 'string'
          ? (event.payload as { correlation_id: string }).correlation_id
          : undefined,
  });

  if (!incident) {
    return current;
  }

  const next = new Map(current);
  next.set(incident.id, incident);

  if (next.size <= INCIDENT_LIMIT) {
    return next;
  }

  return mapSnapshotIncidents(sortRecentIncidents(next.values()).slice(0, INCIDENT_LIMIT));
}
