// MedienDL service worker — network-first fuer die Shell.
// Grund: Nach einem Update darf der Browser NICHT die alte, gecachte
// Oberflaeche liefern. Cache nur noch als Offline-Fallback.
const CACHE = "mediendl-shell-v2";
const SHELL = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // API-Antworten und Nicht-GET niemals anfassen — immer direkt durchlassen.
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;

  // Network-first: immer frisch vom Server holen; nur bei Netzfehler
  // (offline) auf den Cache zurueckfallen.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || caches.match("/")))
  );
});
