// sw.js — Square Foot (cache apenas de estáticos essenciais)
const CACHE_NAME = "squarefoot-static-v1";

const ASSETS = [
  "/",
  "/icons/favicon.ico",
  "/icons/favicon-16.png",
  "/icons/favicon-32.png",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/site.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))))
    ).then(() => self.clients.claim())
  );
});

// Network-first para HTML; não intercepta a API (pra não “congelar” estatísticas)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Não mexe com chamadas da API (ajusta se tua API tiver outro prefixo)
  if (url.pathname.startsWith("/leagues") || url.pathname.startsWith("/matches") || url.pathname.startsWith("/card")) {
    return;
  }

  // Para navegação/HTML: tenta rede, cai pro cache
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/"))
    );
    return;
  }

  // Para estáticos: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return res;
      });
    })
  );
});
