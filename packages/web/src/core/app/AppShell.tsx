import { NavLink, Outlet } from 'react-router-dom';

export function AppShell() {
  return (
    <div className="min-h-screen bg-surface text-primary-text">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-engine/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <p className="text-xl font-semibold tracking-wide">Emberlog Web</p>
            <p className="text-xs text-white/75">Platform Operations Console</p>
          </div>
          <nav className="flex items-center gap-2">
            <NavLink
              to="/traffic"
              className={({ isActive }) =>
                [
                  'rounded-lg px-3 py-1.5 text-sm font-medium transition',
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-white/5 text-white/80 hover:bg-white/10 hover:text-white',
                ].join(' ')
              }
            >
              Traffic
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
