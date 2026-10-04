const CACHE_NAME = 'spyeye-v3-history-season-fix';
const ASSETS_TO_CACHE = [
  '/',
  '/shared/common.css',
  '/mobile/css/mobile.css',
  '/mobile/js/app.js?v=20260814-history-season3'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isAppAsset = /\/(mobile)\/(js|css)\//.test(url.pathname) || url.pathname === '/';
  const isApi = url.pathname.startsWith('/api/');

  if (isApi) {
    event.respondWith(fetch(event.request, { cache: 'no-store' }));
    return;
  }

  if (isAppAsset) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(caches.match(event.request).then(response => response || fetch(event.request)));
});
