import { API_BASE } from "../config";
import type { Incident } from "../types/incident";

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  page: number;
  page_size: number;
}

export interface IncidentQueryParams {
  from_dispatched_at?: string;
  to_dispatched_at?: string;
  incident_type?: string;
  channel?: string;
  units?: string[];
  address_search?: string;
  page?: number;
  page_size?: number;
}

export async function fetchIncidents(
  params: IncidentQueryParams = {}
): Promise<IncidentListResponse> {
  const url = new URL("/api/v1/incidents", API_BASE);
  const searchParams = url.searchParams;

  const page = params.page ?? 1;
  const pageSize = params.page_size ?? 50;

  searchParams.set("page", String(page));
  searchParams.set("page_size", String(pageSize));

  if (params.incident_type) {
    searchParams.set("incident_type", params.incident_type);
  }

  if (params.address_search?.trim()) {
    searchParams.set("address_search", params.address_search.trim());
  }

  if (params.from_dispatched_at) {
    searchParams.set("from_dispatched_at", params.from_dispatched_at);
  }

  if (params.to_dispatched_at) {
    searchParams.set("to_dispatched_at", params.to_dispatched_at);
  }

  if (params.channel) {
    searchParams.set("channel", params.channel);
  }

  if (params.units?.length) {
    params.units.forEach((unit) => searchParams.append("units", unit));
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch incidents (${response.status})`);
  }

  const data = (await response.json()) as IncidentListResponse;
  if (!data?.items || !Array.isArray(data.items)) {
    throw new Error("Invalid response from incidents API");
  }

  return data;
}
