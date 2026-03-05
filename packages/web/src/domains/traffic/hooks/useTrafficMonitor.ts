import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEventStream } from '../../../core/realtime/useEventStream';
import type { EventEnvelope } from '../../../core/realtime/types';
import { fetchTrafficSummary } from '../api';
import type {
  LiveCall,
  TrafficCallPayload,
  TrafficDecodeRateUpdatedPayload,
  TrafficDecodeSite,
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

function decodeStatusFromPct(decodeRatePct: number): string {
  if (decodeRatePct >= 90) {
    return 'ok';
  }
  if (decodeRatePct >= 70) {
    return 'warn';
  }
  return 'bad';
}

function toDecodeRatePayload(payload: unknown): TrafficDecodeRateUpdatedPayload | null {
  if (!isObject(payload)) {
    return null;
  }

  const system = payload.system;
  const site = payload.site;
  const decodeRate = payload.decode_rate;
  const controlChannel = payload.control_channel_frequency;

  if (typeof system !== 'string' || typeof site !== 'string' || typeof decodeRate !== 'number') {
    return null;
  }

  if (controlChannel != null && typeof controlChannel !== 'number') {
    return null;
  }

  return {
    system,
    site,
    decode_rate: decodeRate,
    control_channel_frequency: controlChannel ?? null,
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

  const decodeRatePct = payload.decode_rate * 100;
  const updatedSite: TrafficDecodeSite = {
    group: payload.system,
    sys_num: 0,
    sys_name: payload.site,
    decode_rate_pct: decodeRatePct,
    control_channel_mhz:
      typeof payload.control_channel_frequency === 'number'
        ? payload.control_channel_frequency / 1_000_000
        : null,
    interval_s: null,
    updated_at: event.timestamp,
    status: decodeStatusFromPct(decodeRatePct),
  };

  const sites = [...existing.decode_sites];
  const siteIndex = sites.findIndex(
    (site) =>
      normalizeKey(site.group) === normalizeKey(payload.system) &&
      normalizeKey(site.sys_name) === normalizeKey(payload.site)
  );

  if (siteIndex === -1) {
    sites.push(updatedSite);
  } else {
    sites[siteIndex] = {
      ...sites[siteIndex],
      decode_rate_pct: updatedSite.decode_rate_pct,
      control_channel_mhz: updatedSite.control_channel_mhz,
      updated_at: updatedSite.updated_at,
      status: updatedSite.status,
    };
  }

  return {
    ...existing,
    decode_sites: sites,
    last_seen_at: event.timestamp,
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
