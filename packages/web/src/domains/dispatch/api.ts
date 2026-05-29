import { getJson } from '../../core/api/client';
import { normalizeIncident } from './recentIncidents';
import type { DispatchIncident, DispatchIncidentList } from './types';

interface IncidentListProjection {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchDispatchIncidents(): Promise<DispatchIncidentList> {
  const response = await getJson<IncidentListProjection>('/api/v1/incidents?page_size=200');
  const items: DispatchIncident[] = [];

  for (const item of response.items) {
    const incident = normalizeIncident(item);
    if (incident) {
      items.push(incident);
    }
  }

  return {
    items,
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}
