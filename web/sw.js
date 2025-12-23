// web/sw.js
const CACHE_NAME = "square-foot-v2"; // <-- troquei v1 -> v2 para forçar atualizar cache

const CORE_ASSETS = [
  "/",
  "/app.js",
  "/sw.js",
  "/icons/site.webmanifest",
  "/icons/favicon.ico",
  "/icons/favicon-16.png",
  "/icons/favicon-32.png",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/logo.png"
];

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
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(CORE_ASSETS);
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)));
    self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== "GET") return;

  // Não cachear chamadas da API; pega sempre da rede
  if (url.pathname.startsWith("/matches") || url.pathname.startsWith("/leagues")) {
    event.respondWith(fetch(req));
    return;
  }

  // HTML navegação: tenta rede primeiro
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req));
    return;
  }

  // Assets do PWA: cache-first
  if (CORE_ASSETS.includes(url.pathname)) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Default
  event.respondWith(networkFirst(req));
});
