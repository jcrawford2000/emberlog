import { z } from 'zod';
import type { DispatchCategory } from './categories';

export type { DispatchCategory } from './categories';

export const DispatchIncidentSchema = z.object({
  id: z.number(),
  dispatched_at: z.string(),
  special_call: z.boolean(),
  units: z.array(z.string()),
  channel: z.string(),
  incident_type: z.string(),
  address: z.string(),
  source_audio: z.string(),
  original_text: z.string(),
  transcript: z.string(),
  parsed: z.record(z.string(), z.unknown()),
  created_at: z.string(),
  correlation_id: z.string().optional(),
});

export type DispatchIncident = z.infer<typeof DispatchIncidentSchema>;

export interface DispatchIncidentList {
  items: DispatchIncident[];
  total: number;
  page: number;
  page_size: number;
}

export type DispatchTimeFilter = 'live' | '1h' | '4h' | 'all';

export interface DispatchFiltersState {
  q: string;
  time: DispatchTimeFilter;
  cities: string[];
  units: string[];
  types: string[];
  categories: DispatchCategory[];
  channels: string[];
}
