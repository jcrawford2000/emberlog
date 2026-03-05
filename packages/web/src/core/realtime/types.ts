export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'offline';

export interface EventEnvelope<TPayload = unknown> {
  event_id: string;
  event_type: string;
  schema_version: string;
  timestamp: string;
  source: {
    module: string;
    instance: string;
    system?: string;
  };
  payload: TPayload;
  correlation_id?: string;
}

export interface EventStreamFilters {
  domain?: string;
  eventTypes?: string[];
  system?: string;
  site?: string;
}

export interface EventStreamOptions {
  path?: string;
  filters?: EventStreamFilters;
  maxReconnectAttempts?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  onStatusChange?: (status: ConnectionStatus) => void;
  onEvent?: (event: EventEnvelope) => void;
  onInvalidEvent?: (raw: string, reason: string) => void;
  onRetriesExhausted?: () => void;
}
