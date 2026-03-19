/* CyberFeed Service Worker — basic offline caching */
const CACHE_NAME = "cyberfeed-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Network-first for HTML, cache-first for static assets
  if (
    event.request.destination === "style" ||
    event.request.destination === "script" ||
    event.request.destination === "image"
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
