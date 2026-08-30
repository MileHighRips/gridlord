import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import Logo from '../components/Logo';

// Sign in to save your league settings + custom board across devices. Guests can
// skip and use the shared default league. If no backend is reachable (e.g. the
// installed PWA with data baked in), we drop straight into the app as a guest.
export default function SignIn({ onSkip }: { onSkip: () => void }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .health()
      .then(() => setChecking(false))
      .catch(() => onSkip()); // no backend -> enter as guest automatically
  }, [onSkip]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'login') await login(email, password);
      else await register(email, password);
    } catch (err) {
      setError(
        mode === 'login'
          ? 'Incorrect email or password.'
          : (err as Error).message.replace(/^\d+.*?:\s*/, ''),
      );
    } finally {
      setBusy(false);
    }
  }

  if (checking) {
    return (
      <div className="text-muted flex min-h-screen items-center justify-center">
        Loading GRIDLORD…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Logo size={52} />
          <div>
            <div className="font-display text-3xl font-bold tracking-widest">
              GRID<span className="text-gold-400">LORD</span>
            </div>
            <div className="eyebrow mt-1">Fantasy Draft War Room</div>
          </div>
        </div>

        <form onSubmit={submit} className="card space-y-3">
          <div className="bg-ink-900 flex gap-1 rounded-lg p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 rounded-md py-1.5 text-sm font-semibold transition ${
                  mode === m ? 'bg-gold-400 text-ink-950' : 'text-muted hover:text-chalk'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Create account'}
              </button>
            ))}
          </div>

          <label className="block">
            <span className="eyebrow">Email</span>
            <input
              type="email"
              required
              className="input mt-1 w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="block">
            <span className="eyebrow">Password</span>
            <input
              type="password"
              required
              minLength={8}
              className="input mt-1 w-full"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && <p className="text-danger text-sm">{error}</p>}

          <button className="btn w-full justify-center" disabled={busy}>
            {busy ? '…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="text-muted hover:text-chalk w-full text-center text-xs"
          >
            Continue as guest →
          </button>
        </form>
      </div>
    </div>
  );
}
