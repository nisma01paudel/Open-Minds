"use client";

import { useEffect, useRef } from "react";

export type AnyFC = { type: "FeatureCollection"; features: any[] };

const COLOUR: any = [
  "match", ["get", "state"],
  "exceeded", "#ff2d20",
  "approaching", "#ff9f0a",
  "#7c8ba1",
];

// Keyless: OpenFreeMap vector tiles for the basemap, AWS terrarium tiles for real 3D
// terrain. No API key anywhere, so the demo works offline and on unknown wifi.
const BASEMAP = "https://tiles.openfreemap.org/styles/liberty";
const TERRAIN = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

const STATE_LABEL: Record<string, string> = {
  exceeded: "above the threshold",
  approaching: "approaching the threshold",
  below: "below the threshold",
};

export default function SlopeMap({
  data,
  popup,
  focus,
}: {
  data: AnyFC | null;
  popup?: boolean;
  focus?: { lon: number; lat: number; zoom?: number } | null;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const readyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled || !holder.current || mapRef.current) return;

      const map = new maplibregl.Map({
        container: holder.current,
        style: BASEMAP,
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

      map.on("load", () => {
        map.addSource("dem", {
          type: "raster-dem", tiles: [TERRAIN], encoding: "terrarium",
          tileSize: 256, maxzoom: 13,
        });
        map.setTerrain({ source: "dem", exaggeration: 1.35 });

        const firstLabel = map.getStyle().layers.find((l: any) => l.type === "symbol")?.id;
        map.addLayer({
          id: "relief", type: "hillshade", source: "dem",
          paint: {
            "hillshade-exaggeration": 0.45,
            "hillshade-shadow-color": "#0b1220",
            "hillshade-highlight-color": "#e2e8f0",
            "hillshade-accent-color": "#334155",
          },
        }, firstLabel);

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

        map.on("mouseenter", "slopes", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "slopes", () => (map.getCanvas().style.cursor = ""));
        map.on("click", "slopes", (e: any) => {
          if (popup === false) return;
          const p = e.features?.[0]?.properties;
          if (!p) return;
          const [lon, lat] = e.features[0].geometry.coordinates;
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

  return <div id="map" ref={holder} />;
}
