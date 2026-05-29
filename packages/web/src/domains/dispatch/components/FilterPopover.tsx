import { Check, ChevronDown } from 'lucide-react';
import type { ReactNode } from 'react';

interface FilterPopoverProps {
  id: string;
  label: ReactNode;
  count?: number;
  openPopover: string | null;
  setOpenPopover: (id: string | null) => void;
  align?: 'left' | 'right';
  children: ReactNode;
}

interface FilterOptionProps {
  selected: boolean;
  label: string;
  sub?: string;
  dotClass?: string;
  variant?: 'check' | 'radio';
  onClick: () => void;
}

export function FilterPopover({
  id,
  label,
  count = 0,
  openPopover,
  setOpenPopover,
  align = 'left',
  children,
}: FilterPopoverProps) {
  const open = openPopover === id;

  return (
    <div className="relative">
      <button
        type="button"
        className={[
          'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition',
          count > 0
            ? 'border-safety/60 bg-safety/15 text-orange-100'
            : 'border-white/20 bg-white/5 text-white/85 hover:bg-white/10',
        ].join(' ')}
        onClick={() => setOpenPopover(open ? null : id)}
      >
        {label}
        {count > 0 ? (
          <span className="grid h-5 min-w-5 place-items-center rounded-full bg-safety px-1 text-[11px] font-extrabold text-black">
            {count}
          </span>
        ) : null}
        <ChevronDown className="h-4 w-4 text-white/55" aria-hidden />
      </button>
      {open ? (
        <div
          className={[
            'absolute top-[calc(100%+0.4rem)] z-50 w-72 rounded-xl border border-white/20 bg-slate-900 p-2 shadow-2xl',
            align === 'right' ? 'right-0' : 'left-0',
          ].join(' ')}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function FilterOption({
  selected,
  label,
  sub,
  dotClass,
  variant = 'check',
  onClick,
}: FilterOptionProps) {
  return (
    <button
      type="button"
      className={[
        'flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-white/85 hover:bg-white/10',
        selected ? 'bg-white/10 text-white' : '',
      ].join(' ')}
      onClick={onClick}
    >
      {variant === 'radio' ? (
        <span
          className={[
            'grid h-4 w-4 flex-none place-items-center rounded-full border',
            selected ? 'border-safety' : 'border-white/35',
          ].join(' ')}
          aria-hidden
        >
          {selected ? <span className="h-2 w-2 rounded-full bg-safety" /> : null}
        </span>
      ) : (
        <span
          className={[
            'grid h-4 w-4 flex-none place-items-center rounded border',
            selected ? 'border-safety bg-safety text-black' : 'border-white/35',
          ].join(' ')}
          aria-hidden
        >
          {selected ? <Check className="h-3 w-3" /> : null}
        </span>
      )}
      {dotClass ? <span className={`h-2.5 w-2.5 flex-none rounded-sm ${dotClass}`} aria-hidden /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {sub ? <span className="font-mono text-[11px] text-white/45">{sub}</span> : null}
    </button>
  );
}

export function PopoverSearch({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <input
      className="mb-2 w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder-white/45 focus:border-white/25 focus:outline-none"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  );
}
