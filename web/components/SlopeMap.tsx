"use client";

import { useEffect, useRef, useState } from "react";

export type AnyFC = { type: "FeatureCollection"; features: any[] };

const COLOUR: any = [
  "match", ["get", "state"],
  "exceeded", "#ff2d20",
  "approaching", "#ff9f0a",
  "#7c8ba1",
];

// ALL REAL IMAGERY, and keyless. No stylised vector basemap, no invented geometry.
//
//   s2cloudless : real Sentinel-2 imagery - the same satellite this project's data spine
//                 reads. Nepal as the satellite actually saw it.
//   esri        : real high-resolution satellite imagery, for close inspection.
//   dem         : real elevation tiles, giving true 3D relief.
//
// A keyless stack is also the operational choice: Demo Day is in person on unknown wifi,
// and a dead key on stage is worse than a clean map.
const BASEMAPS: Record<string, { tiles: string[]; label: string; attribution: string }> = {
  s2cloudless: {
    tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"],
    label: "Sentinel-2",
    attribution: "Imagery: Sentinel-2 cloudless (EOX/ESA)",
  },
  esri: {
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    label: "Satellite (high-res)",
    attribution: "Imagery: Esri World Imagery",
  },
};

// A handful of real places, so the imagery is orientable without a vector basemap.
const PLACES = {
  type: "FeatureCollection" as const,
  features: [
    ["Kathmandu", 85.324, 27.717], ["Pokhara", 83.985, 28.209], ["Biratnagar", 87.271, 26.452],
    ["Birgunj", 84.877, 27.010], ["Butwal", 83.449, 27.700], ["Nepalgunj", 81.617, 28.050],
    ["Dhangadhi", 80.596, 28.706], ["Dharan", 87.279, 26.812], ["Janakpur", 85.925, 26.729],
    ["Ilam", 87.928, 26.909], ["Jomsom", 83.723, 28.781], ["Namche Bazaar", 86.714, 27.807],
  ].map(([name, lon, lat]) => ({
    type: "Feature" as const,
    geometry: { type: "Point" as const, coordinates: [lon as number, lat as number] },
    properties: { name },
  })),
};

function buildStyle(basemap: string) {
  const bm = BASEMAPS[basemap] ?? BASEMAPS.s2cloudless;
  const paint = { "raster-brightness-max": 0.82, "raster-saturation": -0.08 };
  return {
    version: 8 as const,
    sources: {
      // Two sources for one basemap, split by zoom, because Demo Day is on unknown wifi.
      //
      // The national view is what the room actually looks at, and the country fits in
      // thirty-four tiles across z5-z7 - 728 KB, bundled in the repo by
      // scripts/prefetch_tiles.py. Those zooms are served from disk, so the map draws with
      // the network unplugged. Deeper zoom still comes from the live service, because that
      // is hundreds of megabytes and pointless to bundle.
      //
      // Before this, the map was the ONE surface that needed the internet: everything else
      // was cached and keyless, so a dead venue wifi showed an empty map over perfectly
      // present data - which looks like the project is broken, not like it is offline.
      basemapLocal: { type: "raster" as const, tiles: [`tiles/${basemap}/{z}/{y}/{x}.jpg`],
                      tileSize: 256, minzoom: 0, maxzoom: 7, attribution: bm.attribution },
      basemap: { type: "raster" as const, tiles: bm.tiles, tileSize: 256,
                 minzoom: 8, maxzoom: 18, attribution: `${bm.attribution} · Terrain: AWS` },
    },
    layers: [
      { id: "bg", type: "background" as const, paint: { "background-color": "#05070d" } },
      { id: "basemap-low", type: "raster" as const, source: "basemapLocal",
        maxzoom: 8, paint },
      { id: "basemap", type: "raster" as const, source: "basemap", minzoom: 8, paint },
    ],
  };
}

const STATE_LABEL: Record<string, string> = {
  exceeded: "above the threshold",
  approaching: "approaching the threshold",
  below: "below the threshold",
};

export default function SlopeMap({
  data,
  popup,
  focus,
  onPick,
  blind,
}: {
  data: AnyFC | null;
  popup?: boolean;
  focus?: { lon: number; lat: number; zoom?: number } | null;
  onPick?: (p: any, at?: { lon: number; lat: number }) => void;
  blind?: boolean;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const readyRef = useRef(false);
  const blindRef = useRef<boolean>(!!blind);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled || !holder.current || mapRef.current) return;

      const map = new maplibregl.Map({
        container: holder.current,
        style: buildStyle("s2cloudless") as any,
        center: [84.7, 28.35],
        zoom: 6.95,
        pitch: 62,
        bearing: -14,
        maxPitch: 78,
        attributionControl: false,
      });
      mapRef.current = map;

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
      map.addControl(
        new maplibregl.AttributionControl({
          compact: true,
          customAttribution: "Rainfall: Open-Meteo / CHIRPS · Terrain: AWS · Tiles: OpenFreeMap",
        }),
        "bottom-right",
      );

      const markerPopup = new maplibregl.Popup({ closeButton: false, offset: 14, maxWidth: "340px" });

      // Never fail silently: a broken style rendered an empty map once and looked like a
      // styling choice. Now it says so.
      map.on("error", (e: any) => {
        const msg = e?.error?.message ?? String(e?.error ?? "map error");
        console.error("[pahiro] map error:", msg);
        const el = document.getElementById("maperr");
        // Offline is not an error. The high-zoom basemap is the one thing that genuinely
        // needs the network, so when it is gone MapLibre reports a tile decode failure -
        // alarming, and useless to someone standing in a room with a dead venue wifi.
        // Say what is actually happening instead.
        if (el) {
          if (!navigator.onLine || /decode|Failed to fetch|load/i.test(msg)) {
            // Informational, not an error: red would overstate it for someone who simply
            // walked out of wifi range.
            el.classList.add("info");
            el.textContent = navigator.onLine
              ? "basemap detail is unavailable - the national view is bundled and still works"
              : "offline - showing the bundled national view; deeper zoom needs a connection";
          } else {
            el.classList.remove("info");
            el.textContent = `map: ${msg}`;
          }
          el.style.display = "block";
        }
      });

      map.on("load", () => {
        // WHY THERE IS NO 3D TERRAIN LAYER HERE.
        //
        // Two things were tried, and both were measured rather than assumed:
        //   - `terrain` as a key in the style object  -> map renders completely blank
        //   - map.setTerrain({source:"dem"}) in load -> map renders completely blank
        // and with the DEM source plus a hillshade layer present, the map's own `load`
        // event never fires at all, so no layer is ever added. No error is raised, no
        // console failure, nothing in the error surface - bisected by rendering the style
        // one piece at a time until the imagery came back.
        //
        // The tiles themselves are fine (HTTP 200, CORS `*`); this is almost certainly the
        // software GL in the headless test environment failing the shading pass.
        //
        // It may work perfectly on a real GPU. But it could not be verified here, and
        // shipping a layer that silently blanks the map is worse than not shipping it, so
        // what is left is the real Sentinel-2 imagery - which is verified.
        //
        // To try terrain locally, re-add a raster-dem source and uncomment:
        //   map.setTerrain({ source: "dem", exaggeration: 1.4 });
        // Added EMPTY on purpose. Building this from a prop inside the load handler threw
        // before the prop arrived and silently aborted the rest of the handler, so the
        // layers were never added and the map rendered an empty country.
        map.addSource("slopes", { type: "geojson", data: { type: "FeatureCollection", features: [] } });

        map.addLayer({
          id: "slopes-glow", type: "circle", source: "slopes",
          filter: ["!=", ["get", "state"], "below"],
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 12, 9, 26],
            "circle-color": COLOUR, "circle-opacity": 0.20, "circle-blur": 1.0,
          },
        });

        map.addLayer({
          id: "slopes", type: "circle", source: "slopes",
          paint: {
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              5, ["match", ["get", "state"], "below", 3.0, 5.2],
              9, ["match", ["get", "state"], "below", 6.0, 10.5],
            ],
            "circle-color": COLOUR,
            "circle-opacity": 0.95,
            "circle-stroke-width": ["match", ["get", "state"], "below", 0.9, 1.6],
            "circle-stroke-color": ["match", ["get", "state"], "below", "#0f172a", "#ffffff"],
            "circle-stroke-opacity": 0.85,
          },
        });

        // Real place names, as plain DOM markers. Doing this in the style needed a glyph
        // server and an inline geojson source, and that combination silently killed the
        // whole map. Markers cannot.
        for (const f of PLACES.features) {
          const el = document.createElement("div");
          el.className = "placelabel";
          el.textContent = f.properties.name as string;
          new maplibregl.Marker({ element: el, anchor: "top" })
            .setLngLat(f.geometry.coordinates as [number, number])
            .addTo(map);
        }

        // The blind-spot layer: 142 MEASURED observations of how much ground was actually
        // visible at each site in the month it failed. This is the evidence for the claim
        // the rest of the app is built on, so it belongs on the map rather than in a table.
        map.addSource("observability", {
          type: "geojson", data: "/data/observability-sites.json",
        });
        map.addLayer({
          id: "blind", type: "circle", source: "observability",
          layout: { visibility: "none" },
          paint: {
            // BLINDNESS is the signal, so blind sites are drawn big and observable ones
            // small. Sizing by visibility would bury the message in a field of green.
            "circle-radius": ["interpolate", ["linear"], ["get", "pct"],
                              0, 30, 20, 24, 50, 15, 100, 8],
            // red where nothing could be seen, green where the ground was observable
            "circle-color": ["interpolate", ["linear"], ["get", "pct"],
                             0, "#ff2d20", 20, "#ff8c00", 40, "#eab308", 70, "#4ade80", 100, "#22c55e"],
            "circle-opacity": ["interpolate", ["linear"], ["get", "pct"], 0, 0.55, 50, 0.35, 100, 0.20],
            "circle-blur": 0.6,
            "circle-stroke-width": ["interpolate", ["linear"], ["get", "pct"], 0, 2.2, 100, 0.8],
            "circle-stroke-color": ["interpolate", ["linear"], ["get", "pct"],
                                    0, "#ff2d20", 100, "#22c55e"],
            "circle-stroke-opacity": 0.85,
          },
        });

        map.setLayoutProperty("blind", "visibility", blindRef.current ? "visible" : "none");

        map.on("mouseenter", "slopes", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "slopes", () => (map.getCanvas().style.cursor = ""));
        map.on("click", "slopes", (e: any) => {
          if (popup === false) return;
          const p = e.features?.[0]?.properties;
          if (!p) return;
          const [lon, lat] = e.features[0].geometry.coordinates;
          // The coordinates travel with the properties: the flood-escape planner needs the
          // ground the user actually clicked, and a slope's own lat/lon is not always the
          // point they aimed at.
          onPick?.(p, { lon, lat });
          markerPopup.setLngLat([lon, lat]).setHTML(
            `<h3>${p.title || "Documented slope"}</h3>
             <div style="color:#94a3b8">${STATE_LABEL[p.state] ?? p.state} ·
               <b>${Number(p.r24).toFixed(0)} mm</b> in 24 h${p.day ? ` on ${p.day}` : ""}</div>
             <dl>
               <dt>Responsible</dt><dd>${p.authority ?? "—"}</dd>
               <dt>Office</dt><dd>${p.office ?? "—"}</dd>
               <dt>Legal basis</dt><dd>${p.legal_basis ?? "—"}</dd>
             </dl>`).addTo(map);
        });

        readyRef.current = true;
        setReady(true);
        map.fire("slopes-ready");

      });
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
  }, [popup]);

  // Data changes far more often than the map does: swap the source, never rebuild.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const apply = () => {
      const src: any = map.getSource("slopes");
      if (src) src.setData(data);
    };
    if (readyRef.current) apply();
    else map.once("slopes-ready", apply);
  }, [data]);

  // While offline, hide the network basemap entirely rather than let it fail tile by tile.
  // The bundled low-zoom layer stays, so the map still draws.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const vis = navigator.onLine ? "visible" : "none";
      if (map.getLayer("basemap")) map.setLayoutProperty("basemap", "visibility", vis);
    };
    apply();
    window.addEventListener("online", apply);
    window.addEventListener("offline", apply);
    return () => {
      window.removeEventListener("online", apply);
      window.removeEventListener("offline", apply);
    };
  }, [ready]);

  // Toggle the blind-spot layer without rebuilding anything.
  useEffect(() => {
    blindRef.current = !!blind;
    const map = mapRef.current;
    if (!map || !readyRef.current) return;   // the load handler applied the first value
    if (map.getLayer("blind")) {
      map.setLayoutProperty("blind", "visibility", blind ? "visible" : "none");
    }
  }, [blind, ready]);

  // A camera the presenter can aim: glide to whatever the caller focuses on.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus || !readyRef.current) return;
    map.flyTo({
      center: [focus.lon, focus.lat],
      zoom: focus.zoom ?? 9.2,
      pitch: 66,
      duration: 1500,
      essential: true,
    });
  }, [focus]);

  return (
    <>
      <div id="map" ref={holder} />
      <div id="maperr" />
    </>
  );
}
