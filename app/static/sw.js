/* Service worker: estáticos en caché, páginas visitadas disponibles sin conexión, página offline amigable. */
const VERSION = 'v1';
const STATIC = 'static-' + VERSION;
const PAGES = 'pages-' + VERSION;
const PRECACHE = ['/offline', '/static/css/app.css', '/static/js/app.js', '/static/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(STATIC).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => ![STATIC, PAGES].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/panel') || url.pathname === '/publicar') return;

  // Estáticos y fotos: caché primero
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(STATIC).then((c) => c.put(req, copy));
        return res;
      }))
    );
    return;
  }

  // Páginas: red primero, guarda copia; sin red usa la copia o la página offline
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(PAGES).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('/offline')))
    );
  }
});
