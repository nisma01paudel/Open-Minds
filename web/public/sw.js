/* Pahiro Watch service worker.
 *
 * The whole point is that Demo Day is in person on unknown wifi. The season data is
 * ~700 KB and the app shell is small, so both are cached: after one visit the replay,
 * the live map boundaries and the phone view all work with the network unplugged.
 *
 * Data is cache-first (it does not change on a given day). HTML is network-first with a
 * cache fallback, so a stale page is never served while the network is up.
 */
const VERSION = "pahiro-v3";
const SHELL = ["/", "/ar/", "/manifest.webmanifest",
               "/icons/icon-192.png", "/icons/icon-512.png"];
// EVERYTHING the app reads, not three files of it.
//
// This list used to hold three JSON files, and the others were cached only if something happened
// to fetch them - so a browser that went offline before opening the 3D view had no terrain, and
// one that never toggled the trails on had no trail network. "Works offline" was true of the
// paths someone had already walked.
//
// 4.2 MB in total: 1.7 MB of JSON and terrain, 5.4 MB of trail vectors, 1.1 MB of slope geometry.
// That is a deliberate cost. This app is meant to be installed and then work with the radio off,
// and a partial cache is worse than an honest download because it fails at the moment it is
// needed rather than at the moment it is installed.
const DATA = [
  "/data/frames.json",
  "/data/timeline.json",
  "/data/observability-by-month.json",
  "/data/observability-sites.json",
  "/data/advisories.json",
  "/data/terrain.json",
  "/data/terrain.bin",
  "/data/trails.geojson",
  "/data/bus-parks.geojson",
  "/data/slopes-live-2026-09-30.geojson",
  "/data/slopes-chirps-2024-09-28.geojson",
  "/data/slopes-chirps-2024-07-06.geojson",
];

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);

    // ONE AT A TIME, ON PURPOSE.
    //
    // `addAll` is atomic: if ANY url in the list fails, the whole call rejects and NOTHING is
    // cached. With the previous `.catch(() => {})` on top of that, a single renamed file meant a
    // silent, completely empty offline cache - and the app would look fine online right up until
    // the moment it mattered. Adding individually means one bad path costs one file.
    const failed = [];
    for (const u of [...SHELL, ...DATA]) {
      try {
        await c.add(new Request(u, { cache: "reload" }));
      } catch {
        failed.push(u);
      }
    }
    if (failed.length) {
      // Loud, because a missing cached file is exactly the failure this worker exists to prevent.
      console.warn("pahiro: could not precache", failed.length, "of",
                   SHELL.length + DATA.length, "files:", failed);
    }
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
      // Miss with no network: an empty JSON object for a JSON file, and a real error for
      // anything else. The old fallback answered "{}" to every path, including terrain.bin - a
      // binary elevation grid - so a caller that read it as terrain got a two-byte object and no
      // indication that anything was wrong.
      if (url.pathname.endsWith(".json") || url.pathname.endsWith(".geojson")) {
        return hit ?? (await network) ?? new Response("{}", {
          headers: { "Content-Type": "application/json" },
        });
      }
      return hit ?? (await network) ?? Response.error();
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
