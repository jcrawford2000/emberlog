// --- Env Config -----------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://joshua.pi-rack.com:8080";
const trim = (s: string) => s.replace(/\/+$/,"");
export const STREAM_PATH = "/api/v1/sse/incidents";
export const STREAM_URL = API_BASE ? `${trim(API_BASE)}${STREAM_PATH}` : STREAM_PATH;
