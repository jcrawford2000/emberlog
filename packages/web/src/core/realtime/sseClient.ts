import { API_BASE_URL } from '../api/client';
import type { ConnectionStatus, EventEnvelope, EventStreamFilters, EventStreamOptions } from './types';

const DEFAULT_SSE_PATH = '/api/v1/sse';
const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_INITIAL_BACKOFF_MS = 1000;
const DEFAULT_MAX_BACKOFF_MS = 15000;
const DEDUPE_CACHE_SIZE = 1000;

interface ParsedEnvelopeResult {
  envelope: EventEnvelope | null;
  reason?: string;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function buildSseUrl(path: string, filters: EventStreamFilters | undefined, lastEventId: string | null): string {
  const url = new URL(path, API_BASE_URL);

  if (filters?.domain) {
    url.searchParams.set('domain', filters.domain);
  }

  if (filters?.eventTypes?.length) {
    for (const eventType of filters.eventTypes) {
      if (eventType.trim()) {
        url.searchParams.append('event_type', eventType.trim());
      }
    }
  }

  if (filters?.system) {
    url.searchParams.set('system', filters.system);
  }

  if (filters?.site) {
    url.searchParams.set('site', filters.site);
  }

  if (lastEventId) {
    url.searchParams.set('last_event_id', lastEventId);
  }

  return url.toString();
}

function parseEnvelope(rawData: string): ParsedEnvelopeResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawData);
  } catch {
    return { envelope: null, reason: 'invalid JSON payload' };
  }

  if (!isObject(parsed)) {
    return { envelope: null, reason: 'payload is not an object' };
  }

  const eventId = parsed.event_id;
  const eventType = parsed.event_type;
  const schemaVersion = parsed.schema_version;
  const timestamp = parsed.timestamp;
  const source = parsed.source;
  const payload = parsed.payload;

  if (typeof eventId !== 'string' || !eventId) {
    return { envelope: null, reason: 'missing required field: event_id' };
  }
  if (typeof eventType !== 'string' || !eventType) {
    return { envelope: null, reason: 'missing required field: event_type' };
  }
  if (typeof schemaVersion !== 'string' || !schemaVersion) {
    return { envelope: null, reason: 'missing required field: schema_version' };
  }
  if (typeof timestamp !== 'string' || !timestamp) {
    return { envelope: null, reason: 'missing required field: timestamp' };
  }
  if (!isObject(source)) {
    return { envelope: null, reason: 'missing required field: source' };
  }
  if (!('payload' in parsed)) {
    return { envelope: null, reason: 'missing required field: payload' };
  }

  return {
    envelope: {
      event_id: eventId,
      event_type: eventType,
      schema_version: schemaVersion,
      timestamp,
      source: {
        module: String(source.module ?? ''),
        instance: String(source.instance ?? ''),
        system: typeof source.system === 'string' ? source.system : undefined,
      },
      payload,
      correlation_id: typeof parsed.correlation_id === 'string' ? parsed.correlation_id : undefined,
    },
  };
}

export function subscribeToEventStream(options: EventStreamOptions): () => void {
  const {
    path = DEFAULT_SSE_PATH,
    filters,
    maxReconnectAttempts = DEFAULT_MAX_RECONNECT_ATTEMPTS,
    initialBackoffMs = DEFAULT_INITIAL_BACKOFF_MS,
    maxBackoffMs = DEFAULT_MAX_BACKOFF_MS,
    onStatusChange,
    onEvent,
    onInvalidEvent,
    onRetriesExhausted,
  } = options;

  if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
    onStatusChange?.('offline');
    onRetriesExhausted?.();
    return () => {};
  }

  let source: EventSource | null = null;
  let reconnectTimer: number | null = null;
  let reconnectAttempts = 0;
  let lastEventId: string | null = null;
  let closed = false;
  let status: ConnectionStatus = 'connecting';
  const seenEventIds = new Set<string>();
  const seenEventOrder: string[] = [];

  const setStatus = (next: ConnectionStatus) => {
    if (status === next) {
      return;
    }
    status = next;
    onStatusChange?.(next);
  };

  const rememberEventId = (eventId: string): boolean => {
    if (seenEventIds.has(eventId)) {
      return false;
    }
    seenEventIds.add(eventId);
    seenEventOrder.push(eventId);
    if (seenEventOrder.length > DEDUPE_CACHE_SIZE) {
      const oldest = seenEventOrder.shift();
      if (oldest) {
        seenEventIds.delete(oldest);
      }
    }
    return true;
  };

  const closeCurrentSource = () => {
    if (source) {
      source.close();
      source = null;
    }
  };

  const scheduleReconnect = () => {
    reconnectAttempts += 1;
    if (reconnectAttempts > maxReconnectAttempts) {
      setStatus('offline');
      onRetriesExhausted?.();
      return;
    }

    setStatus('reconnecting');
    const backoffMs = Math.min(initialBackoffMs * 2 ** (reconnectAttempts - 1), maxBackoffMs);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      if (!closed) {
        connect();
      }
    }, backoffMs);
  };

  const handleMessage = (event: MessageEvent) => {
    const rawData = typeof event.data === 'string' ? event.data : '';
    const parsed = parseEnvelope(rawData);
    if (!parsed.envelope) {
      const reason = parsed.reason ?? 'invalid envelope';
      console.warn(`Ignoring invalid SSE event: ${reason}`);
      onInvalidEvent?.(rawData, reason);
      return;
    }

    if (!rememberEventId(parsed.envelope.event_id)) {
      return;
    }

    lastEventId = parsed.envelope.event_id;
    onEvent?.(parsed.envelope);
  };

  const connect = () => {
    closeCurrentSource();
    setStatus(reconnectAttempts > 0 ? 'reconnecting' : 'connecting');
    const url = buildSseUrl(path, filters, lastEventId);
    source = new EventSource(url, { withCredentials: false });

    source.onopen = () => {
      reconnectAttempts = 0;
      setStatus('live');
    };

    source.onerror = () => {
      if (closed) {
        return;
      }
      closeCurrentSource();
      scheduleReconnect();
    };

    source.onmessage = handleMessage;

    const eventTypes = filters?.eventTypes ?? [];
    for (const eventType of eventTypes) {
      source.addEventListener(eventType, handleMessage as EventListener);
    }
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    closeCurrentSource();
  };
}
