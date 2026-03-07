import { useMemo } from 'react';
import { SystemHealthCard } from './SystemHealthCard';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthStripProps {
  sites: TrafficDecodeSite[];
  nowMs: number;
}

function compareSites(a: TrafficDecodeSite, b: TrafficDecodeSite): number {
  const bySystemNumber = a.sys_num - b.sys_num;
  if (bySystemNumber !== 0) {
    return bySystemNumber;
  }
  return a.sys_name.localeCompare(b.sys_name);
}

export function SystemHealthStrip({ sites, nowMs }: SystemHealthStripProps) {
  const sortedSites = useMemo(() => [...sites].sort(compareSites), [sites]);

  return (
    <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
      {sortedSites.map((site) => (
        <SystemHealthCard key={`${site.group}-${site.sys_name}-${site.sys_num}`} site={site} nowMs={nowMs} />
      ))}
    </section>
  );
}
