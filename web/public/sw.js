/* Pahiro Watch service worker.
 *
 * The whole point is that Demo Day is in person on unknown wifi. The season data is
 * ~700 KB and the app shell is small, so both are cached: after one visit the replay,
 * the live map boundaries and the phone view all work with the network unplugged.
 *
 * Data is cache-first (it does not change on a given day). HTML is network-first with a
 * cache fallback, so a stale page is never served while the network is up.
 */
const VERSION = "pahiro-v2";
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
  if (e.request.method !== "GET") return;

  // Cross-origin BASEMAP TILES: cache-first, in their own bucket.
  //
  // These are the only third-party requests the app makes, and they used to be ignored
  // outright by the origin check below - so panning around while online cached nothing, and
  // the map came up empty the moment the network went away. Opaque responses are fine to
  // cache here: we only ever read them back through the same tile URL.
  const TILE_HOSTS = ["tiles.maps.eox.at", "server.arcgisonline.com", "s3.amazonaws.com"];
  if (TILE_HOSTS.includes(url.hostname)) {
    e.respondWith((async () => {
      const cache = await caches.open(`${VERSION}-tiles`);
      const hit = await cache.match(e.request);
      if (hit) return hit;
      try {
        const res = await fetch(e.request);
        if (res.ok || res.type === "opaque") cache.put(e.request, res.clone());
        return res;
      } catch {
        const local = await caches.match("/tiles/" + (url.hostname.includes("eox") ? "s2cloudless" : "esri") + "/" + url.pathname.split("/").slice(-3).join("/"));
        return local ?? Response.error();
      }
    })());
    return;
  }

  if (url.origin !== location.origin) return;

  // Data and icons: STALE-WHILE-REVALIDATE.
  //
  // Cache-first was wrong here. The offline demo needs a cached copy, but regenerating the
  // data and rebuilding the app left the browser serving the previous file indefinitely -
  // the advisory panel showed the old text and looked like a rendering bug. This serves
  // the cache immediately (so offline still works) and refreshes it in the background (so
  // a rebuild is picked up on the next load).
  if (url.pathname.startsWith("/data/") || url.pathname.startsWith("/icons/")) {
    e.respondWith((async () => {
      const cache = await caches.open(VERSION);
      const hit = await cache.match(e.request);
      const network = fetch(e.request).then((res) => {
        if (res.ok) cache.put(e.request, res.clone());
        return res;
      }).catch(() => null);
      return hit ?? (await network) ?? new Response("{}", {
        headers: { "Content-Type": "application/json" },
      });
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
