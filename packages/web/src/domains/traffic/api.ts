import { getJson } from '../../core/api/client';
import type { EventEnvelope } from '../../core/realtime/types';
import type { TrafficSummary } from './types';

type DecodeSitesSnapshotPayload = {
  decode_sites: TrafficSummary['decode_sites'];
};

export async function fetchTrafficSummary(instanceId?: string): Promise<TrafficSummary> {
  const params = new URLSearchParams();

  if (instanceId?.trim()) {
    params.set('instance_id', instanceId.trim());
  }

  const query = params.toString();
  const path = query ? `/api/v1/traffic/summary?${query}` : '/api/v1/traffic/summary';
  const envelope = await getJson<EventEnvelope<DecodeSitesSnapshotPayload>>(path);
  return {
    decode_sites: envelope.payload.decode_sites,
  };
}
