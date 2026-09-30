/* Pahiro Watch service worker.
 *
 * The whole point is that Demo Day is in person on unknown wifi. The season data is
 * ~700 KB and the app shell is small, so both are cached: after one visit the replay,
 * the live map boundaries and the phone view all work with the network unplugged.
 *
 * Data is cache-first (it does not change on a given day). HTML is network-first with a
 * cache fallback, so a stale page is never served while the network is up.
 */
const VERSION = "pahiro-v1";
const SHELL = ["/", "/ar/", "/manifest.webmanifest",
               "/icons/icon-192.png", "/icons/icon-512.png"];
const DATA = ["/data/frames.json", "/data/timeline.json", "/data/observability-by-month.json"];

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" }))).catch(() => {});
    await c.addAll(DATA.map((u) => new Request(u, { cache: "reload" }))).catch(() => {});
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  // data + icons: cache first, they are stable for the day
  if (url.pathname.startsWith("/data/") || url.pathname.startsWith("/icons/")) {
    e.respondWith((async () => {
      const hit = await caches.match(e.request);
      if (hit) return hit;
      try {
        const res = await fetch(e.request);
        if (res.ok) (await caches.open(VERSION)).put(e.request, res.clone());
        return res;
      } catch {
        return new Response("{}", { headers: { "Content-Type": "application/json" } });
      }
    })());
    return;
  }

  // everything else: network first, fall back to cache, then to the app shell
  e.respondWith((async () => {
    try {
      const res = await fetch(e.request);
      if (res.ok && url.origin === location.origin) {
        (await caches.open(VERSION)).put(e.request, res.clone());
      }
      return res;
    } catch {
      const hit = await caches.match(e.request);
      if (hit) return hit;
      const shell = await caches.match("/");
      return shell ?? Response.error();
    }
  })());
});
