import type { EventEnvelope } from '../../../core/realtime/types';
import type { TrafficLiveCall } from '../types';

function normalizeSystemKey(value: string): string {
  return value.trim().toLowerCase();
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toLiveCallEventPayload(payload: unknown): { call_id: string; system: string } | null {
  if (!isObject(payload)) {
    return null;
  }

  const system = payload.system;
  const callId = payload.call_id;

  if (typeof system !== 'string' || typeof callId !== 'string') {
    return null;
  }

  return {
    call_id: callId,
    system,
  };
}

export function mapLiveCallSystems(liveCalls: TrafficLiveCall[]): Map<string, string> {
  return new Map(liveCalls.map((call) => [call.id, call.sys_name]));
}

export function countActiveCallsFromSystemMap(liveCallSystemsById: Map<string, string>): Record<string, number> {
  return [...liveCallSystemsById.values()].reduce<Record<string, number>>((counts, system) => {
    const key = normalizeSystemKey(system);
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

export function reduceLiveCallSystems(
  current: Map<string, string>,
  event: EventEnvelope
): Map<string, string> {
  const payload = toLiveCallEventPayload(event.payload);
  if (!payload) {
    return current;
  }

  const next = new Map(current);
  if (event.event_type === 'traffic.call.started') {
    next.set(payload.call_id, payload.system);
    return next;
  }

  if (event.event_type === 'traffic.call.ended') {
    next.delete(payload.call_id);
  }

  return next;
}
