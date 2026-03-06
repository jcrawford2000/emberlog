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
  decode_sites: TrafficDecodeSite[];
}

export type TrafficDecodeRateUpdatedPayload = TrafficDecodeSite;

export interface TrafficCallPayload {
  system: string;
  site: string;
  call_id: string;
  trunkgroup_id?: number | string;
  trunkgroup_label?: string;
  frequency?: number;
  duration_seconds?: number;
}
