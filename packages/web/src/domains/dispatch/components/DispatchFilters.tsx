import { Building2, Clock, Radio, Search, Tags, Truck, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { agencyRange, ALL_CITIES, cityOfUnit, citiesOfIncident, unitNumber } from '../units';
import {
  CATEGORY_COLOR_CLASS,
  CATEGORY_DOT_CLASS,
  categoryOfIncidentType,
  DISPATCH_CATEGORIES,
  type DispatchCategory,
} from '../categories';
import {
  type DispatchFiltersState,
  type DispatchIncident,
  type DispatchTimeFilter,
} from '../types';
import { FilterOption, FilterPopover, PopoverSearch } from './FilterPopover';

interface DispatchFiltersProps {
  filters: DispatchFiltersState;
  incidents: DispatchIncident[];
  resultCount: number;
  onChange: (next: DispatchFiltersState) => void;
}

const TIME_OPTIONS: { value: DispatchTimeFilter; label: string }[] = [
  { value: 'all', label: 'All time' },
  { value: 'live', label: 'Live · last 2 min' },
  { value: '1h', label: 'Last hour' },
  { value: '4h', label: 'Last 4 hours' },
];

function includesValue(values: string[], value: string): boolean {
  return values.includes(value);
}

function toggleString(values: string[], value: string): string[] {
  return includesValue(values, value) ? values.filter((item) => item !== value) : [...values, value];
}

function toggleCategory(values: DispatchCategory[], value: DispatchCategory): DispatchCategory[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function byUnitNumber(left: string, right: string): number {
  return (unitNumber(left) ?? Number.MAX_SAFE_INTEGER) - (unitNumber(right) ?? Number.MAX_SAFE_INTEGER);
}

export function DispatchFilters({ filters, incidents, resultCount, onChange }: DispatchFiltersProps) {
  const [openPopover, setOpenPopover] = useState<string | null>(null);
  const [cityQuery, setCityQuery] = useState('');
  const [unitQuery, setUnitQuery] = useState('');

  const activeCities = useMemo(
    () => [...new Set(incidents.flatMap((incident) => citiesOfIncident(incident.units)))],
    [incidents]
  );
  const allUnits = useMemo(
    () => [...new Set(incidents.flatMap((incident) => incident.units))].sort(byUnitNumber),
    [incidents]
  );
  const allTypes = useMemo(
    () => [...new Set(incidents.map((incident) => incident.incident_type))].sort(),
    [incidents]
  );
  const allChannels = useMemo(
    () => [...new Set(incidents.map((incident) => incident.channel))].sort(),
    [incidents]
  );

  const citiesShown = useMemo(() => {
    const query = cityQuery.trim().toLowerCase();
    const base = query
      ? ALL_CITIES.filter((city) => city.toLowerCase().includes(query))
      : [...activeCities, ...ALL_CITIES.filter((city) => !activeCities.includes(city))];
    return base;
  }, [activeCities, cityQuery]);

  const unitsShown = useMemo(() => {
    const query = unitQuery.trim().toLowerCase();
    return allUnits.filter((unit) => unit.toLowerCase().includes(query));
  }, [allUnits, unitQuery]);

  const timeLabel = TIME_OPTIONS.find((option) => option.value === filters.time)?.label ?? 'All time';
  const chips: { key: keyof DispatchFiltersState; label: string; value: string }[] = [
    ...filters.categories.map((value) => ({ key: 'categories' as const, label: 'Category', value })),
    ...filters.types.map((value) => ({ key: 'types' as const, label: 'Type', value })),
    ...filters.cities.map((value) => ({ key: 'cities' as const, label: 'City', value })),
    ...filters.units.map((value) => ({ key: 'units' as const, label: 'Unit', value })),
    ...filters.channels.map((value) => ({ key: 'channels' as const, label: 'Channel', value })),
  ];
  if (filters.time !== 'all') {
    chips.push({ key: 'time', label: 'Time', value: timeLabel });
  }
  const hasFilters = Boolean(filters.q.trim()) || chips.length > 0;

  const clearAll = () =>
    onChange({
      q: '',
      time: 'all',
      cities: [],
      units: [],
      types: [],
      categories: [],
      channels: [],
    });

  const removeChip = (key: keyof DispatchFiltersState, value: string) => {
    if (key === 'time') {
      onChange({ ...filters, time: 'all' });
      return;
    }
    if (key === 'categories') {
      onChange({
        ...filters,
        categories: filters.categories.filter((category) => category !== value),
      });
      return;
    }
    const current = filters[key];
    if (Array.isArray(current)) {
      onChange({ ...filters, [key]: current.filter((item) => item !== value) });
    }
  };

  return (
    <section className="rounded-xl border border-white/10 bg-slate-950/80 p-4">
      {openPopover ? (
        <button
          type="button"
          className="fixed inset-0 z-40 cursor-default"
          aria-label="Close filters"
          onClick={() => setOpenPopover(null)}
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-60 flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/45" aria-hidden />
          <input
            className="w-full rounded-lg border border-white/20 bg-white/5 py-2 pl-9 pr-3 text-sm text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-safety/70"
            value={filters.q}
            onChange={(event) => onChange({ ...filters, q: event.target.value })}
            placeholder="Search address, unit, transcript..."
          />
        </label>

        <FilterPopover
          id="time"
          label={<span className="inline-flex items-center gap-2"><Clock className="h-4 w-4" />{filters.time === 'all' ? 'Time' : timeLabel}</span>}
          openPopover={openPopover}
          setOpenPopover={setOpenPopover}
        >
          <div className="max-h-64 overflow-y-auto">
            {TIME_OPTIONS.map((option) => (
              <FilterOption
                key={option.value}
                selected={filters.time === option.value}
                variant="radio"
                label={option.label}
                onClick={() => {
                  onChange({ ...filters, time: option.value });
                  setOpenPopover(null);
                }}
              />
            ))}
          </div>
        </FilterPopover>

        <FilterPopover
          id="city"
          label={<span className="inline-flex items-center gap-2"><Building2 className="h-4 w-4" />City</span>}
          count={filters.cities.length}
          openPopover={openPopover}
          setOpenPopover={setOpenPopover}
        >
          <PopoverSearch value={cityQuery} onChange={setCityQuery} placeholder="Search all agencies..." />
          <div className="max-h-64 overflow-y-auto">
            {citiesShown.map((city) => (
              <FilterOption
                key={city}
                selected={filters.cities.includes(city)}
                label={city}
                sub={agencyRange(city)}
                onClick={() => onChange({ ...filters, cities: toggleString(filters.cities, city) })}
              />
            ))}
          </div>
        </FilterPopover>

        <FilterPopover
          id="units"
          label={<span className="inline-flex items-center gap-2"><Truck className="h-4 w-4" />Units</span>}
          count={filters.units.length}
          openPopover={openPopover}
          setOpenPopover={setOpenPopover}
        >
          <PopoverSearch value={unitQuery} onChange={setUnitQuery} placeholder="Filter units..." />
          <div className="max-h-64 overflow-y-auto">
            {unitsShown.length > 0 ? (
              unitsShown.map((unit) => (
                <FilterOption
                  key={unit}
                  selected={filters.units.includes(unit)}
                  label={unit}
                  sub={cityOfUnit(unit)}
                  onClick={() => onChange({ ...filters, units: toggleString(filters.units, unit) })}
                />
              ))
            ) : (
              <div className="px-2 py-3 text-sm text-white/55">No units</div>
            )}
          </div>
        </FilterPopover>

        <FilterPopover
          id="types"
          label={<span className="inline-flex items-center gap-2"><Tags className="h-4 w-4" />Type</span>}
          count={filters.types.length}
          openPopover={openPopover}
          setOpenPopover={setOpenPopover}
        >
          <div className="max-h-64 overflow-y-auto">
            {allTypes.map((type) => {
              const category = categoryOfIncidentType(type);
              return (
                <FilterOption
                  key={type}
                  selected={filters.types.includes(type)}
                  label={type}
                  sub={category}
                  dotClass={CATEGORY_DOT_CLASS[category]}
                  onClick={() => onChange({ ...filters, types: toggleString(filters.types, type) })}
                />
              );
            })}
          </div>
        </FilterPopover>

        <FilterPopover
          id="channels"
          label={<span className="inline-flex items-center gap-2"><Radio className="h-4 w-4" />Channel</span>}
          count={filters.channels.length}
          openPopover={openPopover}
          setOpenPopover={setOpenPopover}
          align="right"
        >
          <div className="max-h-64 overflow-y-auto">
            {allChannels.map((channel) => (
              <FilterOption
                key={channel}
                selected={filters.channels.includes(channel)}
                label={channel}
                onClick={() => onChange({ ...filters, channels: toggleString(filters.channels, channel) })}
              />
            ))}
          </div>
        </FilterPopover>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {DISPATCH_CATEGORIES.map((category) => {
          const selected = filters.categories.includes(category);
          return (
            <button
              key={category}
              type="button"
              className={[
                'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition',
                selected ? CATEGORY_COLOR_CLASS[category] : 'border-white/20 bg-white/5 text-white/70 hover:bg-white/10',
              ].join(' ')}
              onClick={() => onChange({ ...filters, categories: toggleCategory(filters.categories, category) })}
            >
              <span className={`h-2.5 w-2.5 rounded-sm ${CATEGORY_DOT_CLASS[category]}`} aria-hidden />
              {category}
            </button>
          );
        })}
        <span className="ml-auto text-sm text-white/55">{resultCount} of {incidents.length} incidents</span>
      </div>

      {hasFilters ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {filters.q.trim() ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">
              <span className="text-white/50">Search:</span>
              {filters.q}
              <button type="button" onClick={() => onChange({ ...filters, q: '' })} aria-label="Remove search filter">
                <X className="h-3.5 w-3.5 text-white/55" />
              </button>
            </span>
          ) : null}
          {chips.map((chip) => (
            <span
              key={`${chip.label}:${chip.value}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold"
            >
              <span className="text-white/50">{chip.label}:</span>
              {chip.value}
              <button type="button" onClick={() => removeChip(chip.key, chip.value)} aria-label={`Remove ${chip.label} filter`}>
                <X className="h-3.5 w-3.5 text-white/55" />
              </button>
            </span>
          ))}
          <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-white/65 hover:text-white" onClick={clearAll}>
            <X className="h-3.5 w-3.5" />
            Clear all
          </button>
        </div>
      ) : null}
    </section>
  );
}
