import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, tokenStore } from '../api/client';

interface AuthState {
  email: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({} as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((u) => setEmail(u.email))
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  async function login(e: string, p: string) {
    const r = await api.login(e, p);
    tokenStore.set(r.access_token);
    setEmail(r.email);
  }
  async function register(e: string, p: string) {
    const r = await api.register(e, p);
    tokenStore.set(r.access_token);
    setEmail(r.email);
  }
  function logout() {
    tokenStore.clear();
    setEmail(null);
  }

  return (
    <AuthContext.Provider value={{ email, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
