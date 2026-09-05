// GRIDLORD service worker — network-first so a new deploy always wins and phones
// never get stranded on a stale cached JS bundle. The cache is only an offline
// fallback, never the source of truth while the network is reachable.
const CACHE = 'gridlord-v5';
const SHELL = ['./', './index.html', './gridlord.svg', './manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.pathname.startsWith('/api')) return;

  // Network-first for everything the app serves (HTML + hashed JS/CSS/assets).
  // Content-hashed filenames make fresh fetches safe, and this guarantees a new
  // build immediately replaces the old one on every device, including phones.
  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() =>
        caches
          .match(request)
          .then((cached) => cached || (request.mode === 'navigate' ? caches.match('./index.html') : undefined)),
      ),
  );
});
