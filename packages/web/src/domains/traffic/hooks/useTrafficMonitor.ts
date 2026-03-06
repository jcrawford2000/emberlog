import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEventStream } from '../../../core/realtime/useEventStream';
import type { EventEnvelope } from '../../../core/realtime/types';
import { fetchTrafficSummary } from '../api';
import {
  sortRecentCalls,
  toTrafficCallPayload,
  upsertRecentCall,
  type RecentCall,
} from '../recentCalls';
import type {
  TrafficDecodeRateUpdatedPayload,
  TrafficSummary,
} from '../types';

const FALLBACK_POLL_INTERVAL_MS = 5000;
const DEFAULT_RECENT_CALLS_LIMIT = 25;
const RECENT_CALLS_LIMIT_OPTIONS = [10, 25, 50, 100] as const;
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

function mergeCallEvent(
  existingCalls: Map<string, RecentCall>,
  event: EventEnvelope,
  limit: number
): Map<string, RecentCall> {
  const payload = toTrafficCallPayload(event.payload);
  if (!payload) {
    return existingCalls;
  }
  return upsertRecentCall(existingCalls, {
    eventType: event.event_type,
    payload,
    timestamp: event.timestamp,
    limit,
  });
}

export function useTrafficMonitor() {
  const [summary, setSummary] = useState<TrafficSummary | null>(null);
  const [callsById, setCallsById] = useState<Map<string, RecentCall>>(new Map());
  const [recentCallsLimit, setRecentCallsLimit] = useState<number>(DEFAULT_RECENT_CALLS_LIMIT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const snapshotInFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const recentCallsLimitRef = useRef(DEFAULT_RECENT_CALLS_LIMIT);

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
      setCallsById((current) => mergeCallEvent(current, event, recentCallsLimitRef.current));
      return;
    }

    if (event.event_type === 'traffic.call.ended') {
      setCallsById((current) => mergeCallEvent(current, event, recentCallsLimitRef.current));
    }
  }, []);

  const updateRecentCallsLimit = useCallback((nextLimit: number) => {
    if (!RECENT_CALLS_LIMIT_OPTIONS.includes(nextLimit as (typeof RECENT_CALLS_LIMIT_OPTIONS)[number])) {
      return;
    }
    recentCallsLimitRef.current = nextLimit;
    setRecentCallsLimit(nextLimit);
    setCallsById((current) => {
      if (current.size <= nextLimit) {
        return current;
      }
      const sorted = sortRecentCalls(current.values());
      return new Map(sorted.slice(0, nextLimit).map((call) => [call.call_id, call]));
    });
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

  const recentCalls = useMemo(() => sortRecentCalls(callsById.values()), [callsById]);

  return {
    summary,
    recentCalls,
    recentCallsLimit,
    recentCallsLimitOptions: [...RECENT_CALLS_LIMIT_OPTIONS],
    setRecentCallsLimit: updateRecentCallsLimit,
    loading,
    error,
    refreshSnapshot,
    lastFetchedAt,
    connectionStatus: status,
    isPollingFallback,
    pollIntervalMs: FALLBACK_POLL_INTERVAL_MS,
  };
}
