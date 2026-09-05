import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth/AuthContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </HashRouter>
  </React.StrictMode>,
);

// Keep the installed app shell in sync with new deploys so phones never get
// stranded on an old cached bundle — and so no manual "clear site data" is ever
// needed. The service worker is network-first (see public/sw.js); here we make
// the hand-off to a freshly deployed worker seamless and automatic.
if ('serviceWorker' in navigator) {
  const SW_RELOAD_KEY = 'gridlord_sw_reloaded';

  // When a new worker takes control (after skipWaiting + clients.claim), reload
  // once so the newest JS/CSS is running. The one-time guard prevents any loop.
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (sessionStorage.getItem(SW_RELOAD_KEY) === '1') return;
    sessionStorage.setItem(SW_RELOAD_KEY, '1');
    window.location.reload();
  });

  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register(
        `${import.meta.env.BASE_URL}sw.js`,
        { scope: import.meta.env.BASE_URL, updateViaCache: 'none' },
      );

      // Actively check for a newer worker on every load and again periodically,
      // so a fresh deploy is picked up automatically without reopening the app.
      registration.update().catch(() => undefined);
      setInterval(() => registration.update().catch(() => undefined), 60_000);
    } catch {
      /* offline support is best-effort */
    }
  });
}
