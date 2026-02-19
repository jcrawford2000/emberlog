import { Incident } from "../types/emberlogTypes";


export function addIncidentDedupeCap(
  nextOne: Incident,
  list: Incident[],
  max = 200
): Incident[] {
  if (list.some((x) => x.id === nextOne.id)) return list;
  const next = [nextOne, ...list];
  // Optional: keep newest first (by dispatched_at) if your server order varies
  next.sort((a, b) => (a.dispatched_at > b.dispatched_at ? -1 : 1));
  return next.slice(0, max);

}
