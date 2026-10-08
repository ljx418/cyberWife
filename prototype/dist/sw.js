const CACHE_VERSION = 'cyberwife-public-shell-v1';
const PUBLIC_PREFIXES = ['/assets/', '/icons/', '/backgrounds/'];
const PUBLIC_EXACT = new Set(['/index.html', '/manifest.webmanifest']);
const PRIVATE_PREFIXES = ['/api/', '/ws/', '/uploads/', '/media/', '/avatars/', '/memories/'];

function sameOrigin(url) {
  return url.origin === self.location.origin;
}

function explicitlyPrivate(request, url) {
  return request.headers.has('authorization')
    || request.headers.has('cookie')
    || PRIVATE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

function publicStaticRequest(request) {
  if (request.method !== 'GET') return false;
  const url = new URL(request.url);
  if (!sameOrigin(url) || explicitlyPrivate(request, url)) return false;
  return PUBLIC_EXACT.has(url.pathname) || PUBLIC_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

function cacheSafeResponse(response) {
  if (!response || !response.ok || response.type === 'opaque') return false;
  const control = (response.headers.get('cache-control') || '').toLowerCase();
  return !control.includes('no-store') && !control.includes('private') && !response.headers.has('set-cookie');
}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(['/index.html', '/manifest.webmanifest'])));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(Promise.all([
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith('cyberwife-public-shell-') && key !== CACHE_VERSION).map((key) => caches.delete(key)))),
    self.clients.claim(),
  ]));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.mode === 'navigate' && request.method === 'GET' && sameOrigin(url) && !explicitlyPrivate(request, url)) {
    event.respondWith(fetch(request).then(async (response) => {
      if (cacheSafeResponse(response)) {
        const cache = await caches.open(CACHE_VERSION);
        await cache.put('/index.html', response.clone());
      }
      return response;
    }).catch(async () => (await caches.match('/index.html')) || Response.error()));
    return;
  }
  if (!publicStaticRequest(request)) return;
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then(async (response) => {
    if (cacheSafeResponse(response)) {
      const cache = await caches.open(CACHE_VERSION);
      await cache.put(request, response.clone());
    }
    return response;
  })));
});
