// web/sw.js
const CACHE_NAME = "square-foot-v2"; // <-- troquei v1 -> v2 para forçar atualização

// Cache mínimo (assets do PWA + principais arquivos)
const CORE_ASSETS = [
  "/",
  "/sw.js",
  "/icons/site.webmanifest",
  "/icons/favicon.ico",
  "/icons/favicon-16.png",
  "/icons/favicon-32.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/square-foot-logo.png",   // <-- tua logo nova
  "/app.js",
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
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
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
      await Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
      self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Só controla o próprio domínio
  if (url.origin !== self.location.origin) return;

  // Para HTML (/) usa network-first (sempre tenta pegar versão nova)
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req));
    return;
  }

  // Para JS/PNG/CSS etc: cache-first
  event.respondWith(cacheFirst(req));
});
