import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchTrafficSummary } from '../api';
import type { TrafficSummary } from '../types';

const POLL_INTERVAL_MS = 5000;

export function useTrafficSummary() {
  const [data, setData] = useState<TrafficSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    if (inFlightRef.current) {
      return;
    }

    inFlightRef.current = true;
    setError(null);

    try {
      const summary = await fetchTrafficSummary();
      if (!mountedRef.current) {
        return;
      }
      setData(summary);
      setLastFetchedAt(Date.now());
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      console.error('Failed to fetch traffic summary', err);
      setError('Unable to load traffic summary right now.');
    } finally {
      if (!mountedRef.current) {
        return;
      }
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();

    const timer = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  return {
    data,
    loading,
    error,
    refresh,
    lastFetchedAt,
    pollIntervalMs: POLL_INTERVAL_MS,
  };
}
