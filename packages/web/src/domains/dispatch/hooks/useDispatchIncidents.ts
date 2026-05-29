import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEventStream } from '../../../core/realtime/useEventStream';
import type { ConnectionStatus, EventEnvelope } from '../../../core/realtime/types';
import { fetchDispatchIncidents } from '../api';
import {
  mapSnapshotIncidents,
  mergeIncidentEvent,
  sortRecentIncidents,
} from '../recentIncidents';
import type { DispatchIncident } from '../types';

const FALLBACK_POLL_INTERVAL_MS = 5000;
const DISPATCH_EVENT_TYPES = ['dispatch.incident.created', 'dispatch.incident.updated'] as const;

export function useDispatchIncidents() {
  const [incidentsById, setIncidentsById] = useState<Map<number, DispatchIncident>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const snapshotInFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const previousConnectionStatusRef = useRef<ConnectionStatus>('connecting');

  const refreshSnapshot = useCallback(async () => {
    if (snapshotInFlightRef.current) {
      return;
    }

    snapshotInFlightRef.current = true;
    try {
      const snapshot = await fetchDispatchIncidents();
      if (!mountedRef.current) {
        return;
      }
      setIncidentsById(mapSnapshotIncidents(snapshot.items));
      setLastFetchedAt(Date.now());
      setError(null);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      console.error('Failed to fetch dispatch incidents', err);
      setError('Unable to load dispatch incidents right now.');
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
    setIncidentsById((current) => mergeIncidentEvent(current, event));
  }, []);

  const stream = useMemo(
    () => ({
      filters: {
        eventTypes: [...DISPATCH_EVENT_TYPES],
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

  const incidents = useMemo(() => sortRecentIncidents(incidentsById.values()), [incidentsById]);

  return {
    incidents,
    loading,
    error,
    refreshSnapshot,
    lastFetchedAt,
    connectionStatus: status,
    isPollingFallback,
    pollIntervalMs: FALLBACK_POLL_INTERVAL_MS,
  };
}
