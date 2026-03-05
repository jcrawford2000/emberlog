import { useEffect, useMemo, useRef, useState } from 'react';
import { subscribeToEventStream } from './sseClient';
import type { ConnectionStatus, EventEnvelope, EventStreamOptions } from './types';

interface UseEventStreamOptions {
  enabled?: boolean;
  stream: Omit<EventStreamOptions, 'onStatusChange' | 'onRetriesExhausted' | 'onEvent'>;
  onEvent?: (event: EventEnvelope) => void;
}

interface UseEventStreamResult {
  status: ConnectionStatus;
  retriesExhausted: boolean;
}

export function useEventStream(options: UseEventStreamOptions): UseEventStreamResult {
  const { enabled = true, stream, onEvent } = options;
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [retriesExhausted, setRetriesExhausted] = useState(false);
  const onEventRef = useRef(onEvent);

  onEventRef.current = onEvent;

  const streamKey = useMemo(() => JSON.stringify(stream), [stream]);

  useEffect(() => {
    if (!enabled) {
      setStatus('offline');
      return () => {};
    }

    setStatus('connecting');
    setRetriesExhausted(false);
    const unsubscribe = subscribeToEventStream({
      ...stream,
      onStatusChange: setStatus,
      onRetriesExhausted: () => {
        setRetriesExhausted(true);
        setStatus('offline');
      },
      onEvent: (event) => onEventRef.current?.(event),
    });

    return () => {
      unsubscribe();
    };
  }, [enabled, streamKey, stream]);

  return { status, retriesExhausted };
}
