import { z } from "zod";

export interface Incident {
  id: number;
  dispatched_at: string; // ISO in UTC
  incident_type: string;
  address: string; // freeform street + city
  units: string[];
  channel: string; // e.g., "PRWC G" or numeric
  source_audio?: string; // URL/path
  transcript?: string;
};

export type IncidentIn = Omit<Incident, "id">;

export interface Paged<T> {
  items: T[];
  total: number;
  nextCursor?: string;
}

export const IncidentSchema = z.object({
  id: z.number(),
  dispatched_at: z.string(),
  incident_type: z.string(),
  address: z.string(),
  units: z.array(z.string()),
  channel: z.string(),
  source_audio: z.string().url().nullable().optional(),
  transcript: z.string().nullable().optional(),
});

/** Safe-parse helper for SSE strings. */
export function parseIncident(json: string): Incident | null {
  try {
    const data = JSON.parse(json);
    const parsed = IncidentSchema.safeParse(data);
    return parsed.success ? (parsed.data as Incident) : null;
  } catch {
    return null;
  }
}
