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
  encrypted?: boolean;
  is_recording?: boolean;
}

export interface TrafficLiveCall {
  id: string;
  started_at: string | null;
  elapsed_s: number;
  sys_num: number | null;
  sys_name: string;
  group: string;
  talkgroup_id: number | null;
  talkgroup: string | null;
  description: string | null;
  category: string | null;
  tag: string | null;
  freq_mhz: number | null;
  encrypted: boolean;
  emergency: boolean;
  phase2_tdma: boolean;
  tdma_slot: number | null;
  unit: number | null;
  src_num: number | null;
  rec_num: number | null;
  recorder_id: string | null;
}

export interface TrafficLiveCallsSnapshot {
  instance_id: string;
  updated_at: string | null;
  calls: TrafficLiveCall[];
}
