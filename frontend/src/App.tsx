import { useState } from 'react';
import { NavLink, Route, Routes } from 'react-router-dom';
import Logo from './components/Logo';
import { useAuth } from './auth/AuthContext';
import SignIn from './pages/SignIn';
import Dashboard from './pages/Dashboard';
import LeagueSettings from './pages/LeagueSettings';
import DraftRoom from './pages/DraftRoom';
import Rankings from './pages/Rankings';
import LineupOptimizer from './pages/LineupOptimizer';
import TradeAnalyzer from './pages/TradeAnalyzer';
import WaiverBoard from './pages/WaiverBoard';
import MultiLeague from './pages/MultiLeague';
import News from './pages/News';
import HiddenGems from './pages/HiddenGems';
import PlayerIntel from './pages/PlayerIntel';
import Sources from './pages/Sources';
import MyBoard from './pages/MyBoard';

const NAV_GROUPS: {
  label: string;
  items: { to: string; label: string; end?: boolean }[];
}[] = [
  {
    label: 'Draft',
    items: [
      { to: '/', label: 'War Room', end: true },
      { to: '/draft', label: 'Live Draft' },
      { to: '/rankings', label: 'Rankings' },
      { to: '/board', label: 'My Board' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/intel', label: 'Player Intel' },
      { to: '/gems', label: 'Hidden Gems' },
      { to: '/news', label: 'News Wire' },
    ],
  },
  {
    label: 'Manage',
    items: [
      { to: '/lineup', label: 'Lineup' },
      { to: '/trades', label: 'Trades' },
      { to: '/waivers', label: 'Waivers' },
      { to: '/multi', label: 'Season Sim' },
      { to: '/settings', label: 'League Setup' },
      { to: '/sources', label: 'Data Sources' },
    ],
  },
];

export default function App() {
  const { email, loading, logout } = useAuth();
  const [guest, setGuest] = useState(() => !!localStorage.getItem('gridlord_guest'));
  const [mobileOpen, setMobileOpen] = useState(false);

  if (loading) {
    return (
      <div className="text-muted flex min-h-screen items-center justify-center">
        Loading…
      </div>
    );
  }
  if (!email && !guest) {
    return (
      <SignIn
        onSkip={() => {
          localStorage.setItem('gridlord_guest', '1');
          setGuest(true);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="border-ink-500/60 bg-ink-900/95 sticky top-0 z-30 flex flex-col border-b px-4 py-3 backdrop-blur lg:h-screen lg:border-b-0 lg:border-r lg:py-4">
        <div className="flex items-center gap-2.5">
          <Logo size={34} />
          <div className="leading-none">
            <div className="font-display text-chalk text-xl font-bold tracking-widest">
              GRID<span className="text-gold-400">LORD</span>
            </div>
            <div className="eyebrow mt-1 hidden sm:block">Draft War Room</div>
          </div>
          <button
            className="btn-ghost ml-auto lg:hidden"
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>

        <nav
          className={`mt-4 flex-1 flex-col gap-5 overflow-y-auto lg:mt-6 lg:flex ${
            mobileOpen ? 'flex' : 'hidden'
          }`}
          aria-label="Primary"
        >
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="eyebrow mb-1.5 px-1">{group.label}</div>
              <div className="flex flex-col gap-0.5">
                {group.items.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition lg:py-1.5 ${
                        isActive
                          ? 'bg-gold-400/10 text-gold-300 shadow-gold-400 shadow-[inset_2px_0_0_0]'
                          : 'text-muted hover:bg-ink-700 hover:text-chalk'
                      }`
                    }
                  >
                    {n.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

          <div className="border-ink-600/60 mt-auto border-t pt-3">
            {email ? (
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-muted truncate" title={email}>
                  {email}
                </span>
                <button className="btn-ghost px-2 py-1" onClick={logout}>
                  Sign out
                </button>
              </div>
            ) : (
              <button
                className="btn-ghost w-full justify-center"
                onClick={() => {
                  localStorage.removeItem('gridlord_guest');
                  setGuest(false);
                }}
              >
                Sign in to save
              </button>
            )}
          </div>
        </nav>
      </aside>

      <main className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/draft" element={<DraftRoom />} />
          <Route path="/rankings" element={<Rankings />} />
          <Route path="/board" element={<MyBoard />} />
          <Route path="/intel" element={<PlayerIntel />} />
          <Route path="/gems" element={<HiddenGems />} />
          <Route path="/news" element={<News />} />
          <Route path="/lineup" element={<LineupOptimizer />} />
          <Route path="/trades" element={<TradeAnalyzer />} />
          <Route path="/waivers" element={<WaiverBoard />} />
          <Route path="/settings" element={<LeagueSettings />} />
          <Route path="/multi" element={<MultiLeague />} />
          <Route path="/sources" element={<Sources />} />
        </Routes>
      </main>
    </div>
  );
}
