// web/sw.js
const CACHE_NAME = "square-foot-v3";

// Cache mínimo (assets do PWA)
const CORE_ASSETS = [
  "/",
  "/index.html",
  "/app.js",
  "/sw.js",
  "/icons/site.webmanifest",
  "/icons/favicon.ico",
  "/icons/favicon-16.png",
  "/icons/favicon-32.png",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/square-foot-logo.png",
];

// Helpers
async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;

  const res = await fetch(request);
  if (res && res.ok) cache.put(request, res.clone());
  return res;
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const res = await fetch(request);
    if (res && res.ok) cache.put(request, res.clone());
    return res;
  } catch (e) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw e;
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(CORE_ASSETS);
      self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))));
      self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Não mexe com coisas de outras origens
  if (url.origin !== self.location.origin) return;

  // API: tenta rede primeiro, cai pro cache se offline
  if (
    url.pathname.startsWith("/leagues") ||
    url.pathname.startsWith("/matches") ||
    url.pathname.startsWith("/standings") ||
    url.pathname.startsWith("/teamstats") ||
    url.pathname.startsWith("/last5")
  ) {
    event.respondWith(networkFirst(req));
    return;
  }

  // Assets: cache primeiro
  event.respondWith(cacheFirst(req));
});
