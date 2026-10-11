// Cache de la interfície. Les notícies i els PDF no es generen sense connexió.
const CACHE = 'el-meu-diari-v7';
const ASSETS = [
  './', './index.html', './manifest.webmanifest',
  './assets/img/icon.png', './assets/img/icon-512.png',
  './assets/css/styles.css', './assets/js/app.js', './assets/js/storage.js', './assets/js/sw.js'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
  );
  self.clients.claim();
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  // Dated editions must never fall back to yesterday’s cached news.
  if (url.pathname.includes('/diaris/')) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy)).catch(() => {});
    }
    return response;
  }).catch(() => caches.match(event.request)));
});
