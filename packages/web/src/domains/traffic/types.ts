export interface TrafficDecodeSite {
  group: string;
  sys_num: number;
  sys_name: string;
  decode_rate_pct: number;
  control_channel_mhz: number | null;
  interval_s: number | null;
  updated_at: string | null;
  status: 'ok' | 'warn' | 'bad' | string;
}

export interface TrafficSummary {
  instance_id: string;
  last_seen_at: string | null;
  active_calls_count: number;
  recorders_total: number;
  recorders_recording: number;
  recorders_idle: number;
  recorders_available: number;
  recorders_updated_at: string | null;
  decode_sites: TrafficDecodeSite[];
}

export interface TrafficDecodeRateUpdatedPayload {
  system: string;
  site: string;
  decode_rate: number;
  control_channel_frequency?: number | null;
}

export interface TrafficCallPayload {
  system: string;
  site: string;
  call_id: string;
  frequency?: number;
}

export interface LiveCall {
  callId: string;
  system: string;
  site: string;
  frequency?: number;
  startedAt: string;
  rawPayload: unknown;
}
