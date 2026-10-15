/* Service worker: estáticos en caché, páginas visitadas disponibles sin conexión, página offline amigable. */
// Súbela cuando cambie ESTE archivo para que los teléfonos descarten la caché anterior.
// (El JS y el CSS no dependen de este número: se piden primero a la red, y sus URLs llevan ?v=<fecha del archivo>.)
const VERSION = 'v2';
const STATIC = 'static-' + VERSION;
const PAGES = 'pages-' + VERSION;
const PRECACHE = ['/offline', '/static/css/app.css', '/static/js/app.js', '/static/manifest.webmanifest'];

// Rutas que nunca se guardan en el teléfono: llevan datos personales, códigos de formularios o el celular de otra persona
const PRIVATE = /^\/(admin|panel|publicar|ingresar|registro|recuperar|verificar-correo|favoritos|notificaciones|busquedas-guardadas|salir)(\/|$)|^\/anuncio\/\d+\/(contacto|whatsapp|cartel|estado)|^\/vendedor\/\d+\/contacto/;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(STATIC).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => ![STATIC, PAGES].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const noStore = (res) => /no-store/.test(res.headers.get('Cache-Control') || '');

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (PRIVATE.test(url.pathname)) return;

  if (url.pathname.startsWith('/static/')) {
    // Código (JS, CSS, manifiesto): red primero, para no quedarse nunca con una versión vieja. Sin red, la última copia.
    if (/\.(js|css|webmanifest)$/.test(url.pathname)) {
      e.respondWith(
        fetch(req).then((res) => {
          if (res.ok) { const copy = res.clone(); caches.open(STATIC).then((c) => c.put(req, copy)); }
          return res;
        }).catch(() => caches.match(req, { ignoreSearch: true }))
      );
      return;
    }
    // Fotos e iconos (sus nombres no cambian nunca): caché primero
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(STATIC).then((c) => c.put(req, copy)); }
        return res;
      }))
    );
    return;
  }

  // Páginas: red primero, guarda copia; sin red usa la copia o la página offline
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok && !noStore(res)) { const copy = res.clone(); caches.open(PAGES).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('/offline')))
    );
  }
});
