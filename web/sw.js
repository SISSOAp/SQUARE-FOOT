// web/sw.js
const CACHE_NAME = "square-foot-v3";

// Arquivos essenciais do app (inclui logo e manifest com ?v=3)
const CORE_ASSETS = [
  "/",
  "/app.js?v=3",
  "/icons/square-foot-logo.png?v=3",
  "/icons/site.webmanifest?v=3"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Nunca cachear API
  if (url.pathname.startsWith("/api")) return;

  // Navegação: tenta rede primeiro, cai para cache
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("/"))
    );
    return;
  }

  // Assets: cache-first
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        // só cacheia GET ok
        if (req.method === "GET" && res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        }
        return res;
      });
    })
  );
});
