import { useMemo } from 'react';
import { SystemHealthCard } from './SystemHealthCard';
import type { TrafficDecodeSite } from '../types';

interface SystemHealthStripProps {
  sites: TrafficDecodeSite[];
  activeCallsBySystem: Record<string, number>;
  nowMs: number;
  selectedSystem: string | null;
  onSelectSystem: (system: string) => void;
}

function compareSites(a: TrafficDecodeSite, b: TrafficDecodeSite): number {
  const bySystemNumber = a.sys_num - b.sys_num;
  if (bySystemNumber !== 0) {
    return bySystemNumber;
  }
  return a.sys_name.localeCompare(b.sys_name);
}

function normalizeSystemKey(value: string): string {
  return value.trim().toLowerCase();
}

export function SystemHealthStrip({
  sites,
  activeCallsBySystem,
  nowMs,
  selectedSystem,
  onSelectSystem,
}: SystemHealthStripProps) {
  const sortedSites = useMemo(() => [...sites].sort(compareSites), [sites]);

  return (
    <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
      {sortedSites.map((site) => (
        <SystemHealthCard
          key={`${site.group}-${site.sys_name}-${site.sys_num}`}
          site={site}
          nowMs={nowMs}
          activeCallsCount={activeCallsBySystem[normalizeSystemKey(site.sys_name)] ?? 0}
          isSelected={selectedSystem === site.sys_name}
          onSelect={() => onSelectSystem(site.sys_name)}
        />
      ))}
    </section>
  );
}
