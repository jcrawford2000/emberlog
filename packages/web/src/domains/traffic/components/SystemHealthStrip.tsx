import { useMemo } from 'react';
import { SystemHealthCard } from './SystemHealthCard';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthStripProps {
  sites: TrafficDecodeSite[];
  nowMs: number;
}

function compareSites(a: TrafficDecodeSite, b: TrafficDecodeSite): number {
  const byGroup = a.group.localeCompare(b.group);
  if (byGroup !== 0) {
    return byGroup;
  }

  const byName = a.sys_name.localeCompare(b.sys_name);
  if (byName !== 0) {
    return byName;
  }

  return a.sys_num - b.sys_num;
}

export function SystemHealthStrip({ sites, nowMs }: SystemHealthStripProps) {
  const sortedSites = useMemo(() => [...sites].sort(compareSites), [sites]);

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {sortedSites.map((site) => (
        <SystemHealthCard key={`${site.group}-${site.sys_name}-${site.sys_num}`} site={site} nowMs={nowMs} />
      ))}
    </section>
  );
}
