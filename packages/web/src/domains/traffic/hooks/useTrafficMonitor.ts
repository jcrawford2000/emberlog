import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEventStream } from '../../../core/realtime/useEventStream';
import type { EventEnvelope } from '../../../core/realtime/types';
import { fetchTrafficSummary } from '../api';
import type {
  LiveCall,
  TrafficCallPayload,
  TrafficDecodeRateUpdatedPayload,
  TrafficSummary,
} from '../types';

const FALLBACK_POLL_INTERVAL_MS = 5000;
const TRAFFIC_EVENT_TYPES = [
  'system.site.decode_rate.updated',
  'traffic.call.started',
  'traffic.call.ended',
] as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function normalizeKey(value: string): string {
  return value.trim().toLowerCase();
}

function toDecodeRatePayload(payload: unknown): TrafficDecodeRateUpdatedPayload | null {
  if (!isObject(payload)) {
    return null;
  }

  const group = payload.group;
  const sysNum = payload.sys_num;
  const sysName = payload.sys_name;
  const decodeRatePct = payload.decode_rate_pct;
  const controlChannelMhz = payload.control_channel_mhz;
  const intervalS = payload.interval_s;
  const updatedAt = payload.updated_at;
  const status = payload.status;

  if (
    typeof group !== 'string' ||
    typeof sysNum !== 'number' ||
    typeof sysName !== 'string' ||
    typeof decodeRatePct !== 'number' ||
    typeof status !== 'string'
  ) {
    return null;
  }

  if (controlChannelMhz != null && typeof controlChannelMhz !== 'number') {
    return null;
  }

  if (intervalS != null && typeof intervalS !== 'number') {
    return null;
  }

  if (updatedAt != null && typeof updatedAt !== 'string') {
    return null;
  }

  return {
    group,
    sys_num: sysNum,
    sys_name: sysName,
    decode_rate_pct: decodeRatePct,
    control_channel_mhz: controlChannelMhz ?? null,
    interval_s: intervalS ?? null,
    updated_at: updatedAt ?? null,
    status,
  };
}

function toCallPayload(payload: unknown): TrafficCallPayload | null {
  if (!isObject(payload)) {
    return null;
  }

  const system = payload.system;
  const site = payload.site;
  const callId = payload.call_id;
  const frequency = payload.frequency;

  if (typeof system !== 'string' || typeof site !== 'string' || typeof callId !== 'string') {
    return null;
  }

  if (frequency != null && typeof frequency !== 'number') {
    return null;
  }

  return {
    system,
    site,
    call_id: callId,
    frequency: frequency ?? undefined,
  };
}

function mergeDecodeEvent(existing: TrafficSummary, event: EventEnvelope): TrafficSummary {
  const payload = toDecodeRatePayload(event.payload);
  if (!payload) {
    return existing;
  }

  const sites = [...existing.decode_sites];
  const siteIndex = sites.findIndex(
    (site) =>
      normalizeKey(site.sys_name) === normalizeKey(payload.sys_name) && site.sys_num === payload.sys_num
  );

  if (siteIndex === -1) {
    sites.push(payload);
  } else {
    sites[siteIndex] = {
      ...sites[siteIndex],
      group: payload.group,
      decode_rate_pct: payload.decode_rate_pct,
      control_channel_mhz: payload.control_channel_mhz,
      interval_s: payload.interval_s,
      updated_at: payload.updated_at ?? event.timestamp,
      status: payload.status,
    };
  }

  return {
    ...existing,
    decode_sites: sites,
  };
}

function mergeCallStarted(existingCalls: Map<string, LiveCall>, event: EventEnvelope): Map<string, LiveCall> {
  const payload = toCallPayload(event.payload);
  if (!payload) {
    return existingCalls;
  }

  const nextCalls = new Map(existingCalls);
  nextCalls.set(payload.call_id, {
    callId: payload.call_id,
    system: payload.system,
    site: payload.site,
    frequency: payload.frequency,
    startedAt: event.timestamp,
    rawPayload: event.payload,
  });
  return nextCalls;
}

function mergeCallEnded(existingCalls: Map<string, LiveCall>, event: EventEnvelope): Map<string, LiveCall> {
  const payload = toCallPayload(event.payload);
  if (!payload) {
    return existingCalls;
  }

  if (!existingCalls.has(payload.call_id)) {
    return existingCalls;
  }

  const nextCalls = new Map(existingCalls);
  nextCalls.delete(payload.call_id);
  return nextCalls;
}

export function useTrafficMonitor() {
  const [summary, setSummary] = useState<TrafficSummary | null>(null);
  const [callsById, setCallsById] = useState<Map<string, LiveCall>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const snapshotInFlightRef = useRef(false);
  const mountedRef = useRef(true);

  const refreshSnapshot = useCallback(async () => {
    if (snapshotInFlightRef.current) {
      return;
    }

    snapshotInFlightRef.current = true;
    try {
      const nextSummary = await fetchTrafficSummary();
      if (!mountedRef.current) {
        return;
      }

      setSummary(nextSummary);
      setLastFetchedAt(Date.now());
      setError(null);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      console.error('Failed to fetch traffic summary', err);
      setError('Unable to load traffic summary right now.');
    } finally {
      snapshotInFlightRef.current = false;
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refreshSnapshot();

    return () => {
      mountedRef.current = false;
    };
  }, [refreshSnapshot]);

  const handleEvent = useCallback((event: EventEnvelope) => {
    if (event.event_type === 'system.site.decode_rate.updated') {
      setSummary((current) => (current ? mergeDecodeEvent(current, event) : current));
      return;
    }

    if (event.event_type === 'traffic.call.started') {
      setCallsById((current) => mergeCallStarted(current, event));
      return;
    }

    if (event.event_type === 'traffic.call.ended') {
      setCallsById((current) => mergeCallEnded(current, event));
    }
  }, []);

  const stream = useMemo(
    () => ({
      filters: {
        eventTypes: [...TRAFFIC_EVENT_TYPES],
      },
    }),
    []
  );

  const { status, retriesExhausted } = useEventStream({
    stream,
    onEvent: handleEvent,
  });

  useEffect(() => {
    if (status === 'live') {
      setIsPollingFallback(false);
      return;
    }

    if (retriesExhausted) {
      setIsPollingFallback(true);
    }
  }, [retriesExhausted, status]);

  useEffect(() => {
    if (!isPollingFallback) {
      return () => {};
    }

    const timer = window.setInterval(() => {
      void refreshSnapshot();
    }, FALLBACK_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [isPollingFallback, refreshSnapshot]);

  const liveCalls = useMemo(() => {
    return [...callsById.values()].sort((a, b) => {
      const timestampOrder = new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime();
      if (timestampOrder !== 0) {
        return timestampOrder;
      }
      return a.callId.localeCompare(b.callId);
    });
  }, [callsById]);

  return {
    summary,
    liveCalls,
    loading,
    error,
    refreshSnapshot,
    lastFetchedAt,
    connectionStatus: status,
    isPollingFallback,
    pollIntervalMs: FALLBACK_POLL_INTERVAL_MS,
  };
}
