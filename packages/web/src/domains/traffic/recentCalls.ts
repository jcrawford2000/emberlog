import type { EventEnvelope } from '../../core/realtime/types';

import type { TrafficCallPayload } from './types';

export type RecentCallStatus = 'live' | 'ended';

export interface RecentCall {
  call_id: string;
  system: string;
  trunkgroup_id: number | string | null;
  trunkgroup_label: string | null;
  frequency_hz: number | null;
  duration_seconds: number | null;
  started_at: string | null;
  latest_event_at: string;
  status: RecentCallStatus;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function toTrafficCallPayload(payload: unknown): TrafficCallPayload | null {
  if (!isObject(payload)) {
    return null;
  }

  const system = payload.system;
  const site = payload.site;
  const callId = payload.call_id;
  const trunkgroupId = payload.trunkgroup_id;
  const trunkgroupLabel = payload.trunkgroup_label;
  const frequency = payload.frequency;
  const durationSeconds = payload.duration_seconds;

  if (typeof system !== 'string' || typeof site !== 'string' || typeof callId !== 'string') {
    return null;
  }

  if (trunkgroupId != null && typeof trunkgroupId !== 'string' && typeof trunkgroupId !== 'number') {
    return null;
  }

  if (trunkgroupLabel != null && typeof trunkgroupLabel !== 'string') {
    return null;
  }

  if (frequency != null && typeof frequency !== 'number') {
    return null;
  }

  if (durationSeconds != null && typeof durationSeconds !== 'number') {
    return null;
  }

  return {
    system,
    site,
    call_id: callId,
    trunkgroup_id: trunkgroupId ?? undefined,
    trunkgroup_label: trunkgroupLabel ?? undefined,
    frequency: frequency ?? undefined,
    duration_seconds: durationSeconds ?? undefined,
  };
}

function parseTimestampMs(timestamp: string): number {
  const parsed = Date.parse(timestamp);
  return Number.isFinite(parsed) ? parsed : 0;
}

function compareRecentCalls(left: RecentCall, right: RecentCall): number {
  if (left.status !== right.status) {
    return left.status === 'live' ? -1 : 1;
  }

  const byTimestamp = parseTimestampMs(right.latest_event_at) - parseTimestampMs(left.latest_event_at);
  if (byTimestamp !== 0) {
    return byTimestamp;
  }
  return right.call_id.localeCompare(left.call_id);
}

export function mergeRecentCallEvent(
  existing: RecentCall | undefined,
  options: {
    eventType: EventEnvelope['event_type'];
    payload: TrafficCallPayload;
    timestamp: string;
  }
): RecentCall {
  const { eventType, payload, timestamp } = options;
  const nextStatus: RecentCallStatus = eventType === 'traffic.call.ended' ? 'ended' : 'live';

  return {
    call_id: payload.call_id,
    system: payload.system,
    trunkgroup_id: payload.trunkgroup_id ?? existing?.trunkgroup_id ?? null,
    trunkgroup_label: payload.trunkgroup_label ?? existing?.trunkgroup_label ?? null,
    frequency_hz: payload.frequency ?? existing?.frequency_hz ?? null,
    duration_seconds:
      payload.duration_seconds ?? (nextStatus === 'ended' ? existing?.duration_seconds ?? null : null),
    started_at: existing?.started_at ?? (eventType === 'traffic.call.started' ? timestamp : null),
    latest_event_at: timestamp,
    status: nextStatus,
  };
}

export function sortRecentCalls(calls: Iterable<RecentCall>): RecentCall[] {
  return [...calls].sort(compareRecentCalls);
}

export function upsertRecentCall(
  current: Map<string, RecentCall>,
  options: {
    eventType: EventEnvelope['event_type'];
    payload: TrafficCallPayload;
    timestamp: string;
    limit: number;
  }
): Map<string, RecentCall> {
  const { eventType, payload, timestamp, limit } = options;
  const next = new Map(current);
  const merged = mergeRecentCallEvent(next.get(payload.call_id), {
    eventType,
    payload,
    timestamp,
  });
  next.set(payload.call_id, merged);

  if (next.size <= limit) {
    return next;
  }

  const sorted = sortRecentCalls(next.values());
  return new Map(sorted.slice(0, limit).map((call) => [call.call_id, call]));
}

export function formatFrequencyMhz(frequencyHz: number | null): string {
  if (typeof frequencyHz !== 'number') {
    return 'n/a';
  }
  return `${(frequencyHz / 1_000_000).toFixed(5)} MHz`;
}

export function formatDuration(durationSeconds: number | null, status: RecentCallStatus): string {
  if (typeof durationSeconds === 'number') {
    return `${Math.round(durationSeconds)}s`;
  }
  return status === 'live' ? 'Live' : 'n/a';
}
