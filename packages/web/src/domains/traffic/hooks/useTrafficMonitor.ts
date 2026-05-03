import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEventStream } from '../../../core/realtime/useEventStream';
import type { ConnectionStatus, EventEnvelope } from '../../../core/realtime/types';
import { fetchTrafficLiveCalls, fetchTrafficSummary } from '../api';
import {
  countActiveCallsFromSystemMap,
  mapLiveCallSystems,
  reduceLiveCallSystems,
} from './liveCallSystems';
import {
  sortRecentCalls,
  toTrafficCallPayload,
  upsertRecentCall,
  type RecentCall,
} from '../recentCalls';
import type {
  TrafficDecodeRateUpdatedPayload,
  TrafficLiveCall,
  TrafficLiveCallsSnapshot,
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

function toRecentCallFromLiveCall(
  liveCall: TrafficLiveCall,
  existing: RecentCall | undefined,
  snapshotUpdatedAt: string | null
): RecentCall {
  const latestEventAt = existing?.latest_event_at ?? liveCall.started_at ?? snapshotUpdatedAt ?? new Date().toISOString();

  return {
    call_id: liveCall.id,
    system: liveCall.sys_name,
    site: existing?.site ?? null,
    trunkgroup_id: liveCall.talkgroup_id ?? existing?.trunkgroup_id ?? null,
    trunkgroup_label: liveCall.talkgroup ?? existing?.trunkgroup_label ?? liveCall.description ?? null,
    frequency_hz:
      liveCall.freq_mhz != null ? Math.round(liveCall.freq_mhz * 1_000_000) : existing?.frequency_hz ?? null,
    duration_seconds: null,
    started_at: liveCall.started_at ?? existing?.started_at ?? null,
    latest_event_at: latestEventAt,
    status: 'live',
    encrypted: liveCall.encrypted,
    is_recording: liveCall.recorder_id != null,
  };
}

function reconcileRecentCallsWithLiveSnapshot(
  current: Map<string, RecentCall>,
  liveSnapshot: TrafficLiveCallsSnapshot,
  limit: number
): Map<string, RecentCall> {
  const next = new Map(current);
  const liveIds = new Set<string>();

  for (const liveCall of liveSnapshot.calls) {
    liveIds.add(liveCall.id);
    next.set(
      liveCall.id,
      toRecentCallFromLiveCall(liveCall, next.get(liveCall.id), liveSnapshot.updated_at)
    );
  }

  for (const [callId, call] of next.entries()) {
    if (call.status === 'live' && !liveIds.has(callId)) {
      next.set(callId, {
        ...call,
        status: 'ended',
        is_recording: false,
      });
    }
  }

  const sorted = sortRecentCalls(next.values());
  return new Map(sorted.slice(0, limit).map((call) => [call.call_id, call]));
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
  const liveCallSystemsByIdRef = useRef<Map<string, string>>(new Map());
  const previousConnectionStatusRef = useRef<ConnectionStatus>('connecting');

  const refreshSnapshot = useCallback(async () => {
    if (snapshotInFlightRef.current) {
      return;
    }

    snapshotInFlightRef.current = true;
    try {
      const [nextSummary, liveSnapshot] = await Promise.all([
        fetchTrafficSummary(),
        fetchTrafficLiveCalls(),
      ]);
      if (!mountedRef.current) {
        return;
      }

      setSummary(nextSummary);
      liveCallSystemsByIdRef.current = mapLiveCallSystems(liveSnapshot.calls);
      setCallsById((current) =>
        reconcileRecentCallsWithLiveSnapshot(current, liveSnapshot, recentCallsLimitRef.current)
      );
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
      liveCallSystemsByIdRef.current = reduceLiveCallSystems(liveCallSystemsByIdRef.current, event);
      setCallsById((current) => mergeCallEvent(current, event, recentCallsLimitRef.current));
      return;
    }

    if (event.event_type === 'traffic.call.ended') {
      liveCallSystemsByIdRef.current = reduceLiveCallSystems(liveCallSystemsByIdRef.current, event);
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
    const previousStatus = previousConnectionStatusRef.current;
    if (status === 'live') {
      setIsPollingFallback(false);
      if (lastFetchedAt !== null && previousStatus !== 'live') {
        void refreshSnapshot();
      }
      previousConnectionStatusRef.current = status;
      return;
    }

    if (retriesExhausted) {
      setIsPollingFallback(true);
    }
    previousConnectionStatusRef.current = status;
  }, [lastFetchedAt, refreshSnapshot, retriesExhausted, status]);

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
  const activeCallsBySystem = useMemo(
    () => countActiveCallsFromSystemMap(liveCallSystemsByIdRef.current),
    [callsById, lastFetchedAt]
  );

  return {
    summary,
    recentCalls,
    activeCallsBySystem,
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
