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

// Keep the installed app shell in sync with new deploys so Safari does not keep an
// old cached dashboard that can render as a white screen.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const existing = await navigator.serviceWorker.getRegistrations();
      await Promise.all(existing.map((registration) => registration.unregister()));
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)));

      const registration = await navigator.serviceWorker.register(
        `${import.meta.env.BASE_URL}sw.js`,
        { scope: import.meta.env.BASE_URL },
      );

      const SW_RELOAD_KEY = 'gridlord_sw_reload_done';
      registration.addEventListener('updatefound', () => {
        const installing = registration.installing;
        if (!installing) return;
        installing.addEventListener('statechange', () => {
          if (installing.state === 'activated' && navigator.serviceWorker.controller) {
            if (sessionStorage.getItem(SW_RELOAD_KEY) !== '1') {
              sessionStorage.setItem(SW_RELOAD_KEY, '1');
              window.location.reload();
            }
          }
        });
      });
    } catch {
      /* offline support is best-effort */
    }
  });
}
