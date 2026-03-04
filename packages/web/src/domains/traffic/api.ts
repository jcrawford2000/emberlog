import { getJson } from '../../core/api/client';
import type { TrafficSummary } from './types';

export async function fetchTrafficSummary(instanceId?: string): Promise<TrafficSummary> {
  const params = new URLSearchParams();

  if (instanceId?.trim()) {
    params.set('instance_id', instanceId.trim());
  }

  const query = params.toString();
  const path = query ? `/api/v1/traffic/summary?${query}` : '/api/v1/traffic/summary';
  return getJson<TrafficSummary>(path);
}
