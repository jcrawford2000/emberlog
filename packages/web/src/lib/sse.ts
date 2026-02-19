/* eslint-disable @typescript-eslint/no-explicit-any */
import { STREAM_URL } from "../config";

export type LiveState = "connecting" | "open" | "closed";

export function openIncidentStream(opts: {
  onStatus?: (s: LiveState) => void;
  onIncident: (incidentJson: string) => void;
}) {
  const { onStatus, onIncident } = opts;

  if (typeof window === "undefined" || !(window as any).EventSource) {
    onStatus?.("closed");
    return () => {};
  }

  onStatus?.("connecting");
  const es = new EventSource(STREAM_URL, { withCredentials: false});
  es.onopen = () => onStatus?.("open");
  es.onerror = () => onStatus?.("closed");

  const handleIncident = (ev: MessageEvent) => {
    onIncident(ev.data);
  };

  es.addEventListener("incident", handleIncident as any);

  return () => {
    es.removeEventListener("incident", handleIncident as any);
    es.close();
  }

}
