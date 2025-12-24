// web/sw.js

const CACHE_VERSION = "v7"; // MUDA esse número sempre que mexer
const CACHE_NAME = `square-foot-${CACHE_VERSION}`;

// O que você quer cachear do FRONT
const ASSETS = [
  "/",
  "/app.js",
  "/sw.js",
  "/styles.css",
  "/antd.min.css",
  "/quill.snow.css",
  "/square-foot-logo.png?v=3",
];

// Rotas que NÃO podem ser respondidas pelo cache do SW (API e dados)
function isApiOrData(url) {
  return (
    url.pathname.startsWith("/competitions") ||
    url.pathname.startsWith("/predict") ||
    url.pathname.startsWith("/leagues") ||
    url.pathname.startsWith("/matches") ||
    url.pathname.startsWith("/data/") ||
    url.pathname.startsWith("/icons/")
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("square-foot-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Nunca intercepta API/DATA: sempre vai direto na rede
  if (isApiOrData(url)) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Para o resto (front), usa cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return resp;
      });
    })
  );
});
