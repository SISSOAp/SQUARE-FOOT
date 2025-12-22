// web/sw.js
const CACHE_NAME = "square-foot-v1";

// Cache mínimo (assets do PWA)
const CORE_ASSETS = [
  "/",
  "/sw.js",
  "/icons/site.webmanifest",
  "/icons/favicon-32.png",
  "/icons/favicon-16.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
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
      await Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)));
      self.clients.claim();
    })()
  );
});

// Estratégia:
// - HTML (navegação): network-first (fallback cache)
// - API (/leagues, /matches, /card): network-first (fallback cache)
// - Ícones/arquivos estáticos: cache-first
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Só controla o mesmo domínio
  if (url.origin !== location.origin) return;

  const isApi =
    url.pathname.startsWith("/leagues") ||
    url.pathname.startsWith("/matches") ||
    url.pathname.startsWith("/card");

  const isIcons = url.pathname.startsWith("/icons/");
  const isSW = url.pathname === "/sw.js";

  // Navegação (carregar a página)
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req));
    return;
  }

  // API: prioridade rede, fallback cache
  if (isApi) {
    event.respondWith(networkFirst(req));
    return;
  }

  // Assets: cache-first
  if (isIcons || isSW) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Default
  event.respondWith(cacheFirst(req));
});
