"use client";

import { useEffect, useRef, useState } from "react";

export type Frame = {
  id: string;
  label: string;
  date: string;
  source: string;
  file: string;
  counts: Record<string, number>;
  worst_r24: number;
};

const COLOUR: any = [
  "match", ["get", "state"],
  "exceeded", "#ff3b30",
  "approaching", "#ff9f0a",
  "#64748b",
];

const STATE_LABEL: Record<string, string> = {
  exceeded: "above the threshold",
  approaching: "approaching the threshold",
  below: "below the threshold",
};

// Keyless sources: OpenFreeMap vector tiles for the basemap, AWS terrarium tiles for
// real 3D terrain. No API key anywhere, so the demo works offline and on unknown wifi.
const BASEMAP = "https://tiles.openfreemap.org/styles/liberty";
const TERRAIN_TILES =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export default function SlopeMap({
  frames,
  activeIndex,
  onPick,
}: {
  frames: Frame[];
  activeIndex: number;
  onPick?: (p: any) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("loading terrain…");

  // ---- create the map once ------------------------------------------------
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

      const popup = new maplibregl.Popup({ closeButton: false, offset: 12, maxWidth: "330px" });

      map.on("load", () => {
        // real 3D terrain
        map.addSource("dem", {
          type: "raster-dem",
          tiles: [TERRAIN_TILES],
          encoding: "terrarium",
          tileSize: 256,
          maxzoom: 13,
        });
        map.setTerrain({ source: "dem", exaggeration: 1.35 });

        // relief shading so the Himalaya reads as terrain, not a flat tint
        const firstLabel = map.getStyle().layers.find((l: any) => l.type === "symbol")?.id;
        map.addLayer(
          {
            id: "relief",
            type: "hillshade",
            source: "dem",
            paint: {
              "hillshade-exaggeration": 0.45,
              "hillshade-shadow-color": "#0b1220",
              "hillshade-highlight-color": "#e2e8f0",
              "hillshade-accent-color": "#334155",
            },
          },
          firstLabel,
        );

        // The slopes. The source is added EMPTY on purpose: this handler runs before the
        // frames prop has arrived, so referencing frames[activeIndex].file here threw and
        // silently aborted the rest of the handler - which is why the dots never appeared.
        // The effect below fills the source as soon as the data is available.
        map.addSource("slopes", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        map.addLayer({
          id: "slopes-glow",
          type: "circle",
          source: "slopes",
          filter: ["!=", ["get", "state"], "below"],
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 9, 9, 20],
            "circle-color": COLOUR,
            "circle-opacity": 0.18,
            "circle-blur": 0.9,
          },
        });

        map.addLayer({
          id: "slopes",
          type: "circle",
          source: "slopes",
          paint: {
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              5, ["match", ["get", "state"], "below", 3.0, 5.0],
              9, ["match", ["get", "state"], "below", 6.0, 10.0],
            ],
            "circle-color": COLOUR,
            "circle-opacity": ["match", ["get", "state"], "below", 0.95, 1],
            "circle-stroke-width": ["match", ["get", "state"], "below", 0.9, 1.6],
            "circle-stroke-color": ["match", ["get", "state"], "below", "#1e293b", "#ffffff"],
            "circle-stroke-opacity": 0.85,
          },
        });

        map.on("mouseenter", "slopes", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "slopes", () => (map.getCanvas().style.cursor = ""));
        map.on("click", "slopes", (e: any) => {
          const p = e.features?.[0]?.properties;
          if (!p) return;
          const [lon, lat] = e.features[0].geometry.coordinates;
          popup
            .setLngLat([lon, lat])
            .setHTML(
              `<h3>${p.title || "Documented slope"}</h3>
               <div style="color:#94a3b8">${STATE_LABEL[p.state] ?? p.state} · ${Number(p.r24).toFixed(0)} mm / 24 h</div>
               <dl>
                 <dt>Responsible</dt><dd>${p.authority ?? "—"}</dd>
                 <dt>Office</dt><dd>${p.office ?? "—"}</dd>
                 <dt>Legal basis</dt><dd>${p.legal_basis ?? "—"}</dd>
                 <dt>Source</dt><dd>${p.source}</dd>
               </dl>`,
            )
            .addTo(map);
          onPick?.(p);
        });

        setReady(true);
        setStatus("");
      });

      map.on("error", (e: any) => {
        setStatus(`basemap unavailable — ${e?.error?.message ?? "offline"}`);
      });
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- swap the frame without rebuilding the map ---------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !frames.length) return;
    const frame = frames[activeIndex];
    if (!frame) return;
    const src: any = map.getSource("slopes");
    if (src) src.setData(`/data/${frame.file}`);
  }, [activeIndex, frames, ready]);

  return (
    <>
      <div id="map" ref={holder} />
      {status && <div className="hint">{status}</div>}
    </>
  );
}
