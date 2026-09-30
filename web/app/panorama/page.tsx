"use client";

/**
 * Look around a real valley, offline.
 *
 * Each image in /data/panoramas is an equirectangular render of actual elevation - 2048x1024, 2:1,
 * the standard panorama projection. This projects it through a sphere in a plain 2D canvas: for each
 * screen pixel, work out the ray, convert to the image's coordinates, sample it. No three.js, no
 * network, no tiles - the PNG is in the service worker's precache list, so it is on the device
 * after one visit and stays there with the radio off.
 *
 * Drag to look around. Arrow keys work too, for a presenter who would rather not hunt for a mouse.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const REGIONS = [
  { key: "kathmandu", name: "Kathmandu valley", note: "A broad low valley. The gentlest horizon of the six." },
  { key: "khumbu", name: "Khumbu / Everest", note: "High and steep: 46 degrees of ridge above level." },
  { key: "annapurna", name: "Annapurna", note: "The steepest of the six, at 55 degrees." },
  { key: "langtang", name: "Langtang and Helambu", note: "A long high valley, closed on both sides." },
  { key: "manaslu", name: "Manaslu circuit", note: "A deep gorge: nearly 58 degrees of wall." },
  { key: "mustang", name: "Upper Mustang", note: "High desert. Open, at 24 degrees." },
];

const W = 960, H = 540;           // draw resolution; the source is 2048x1024
const FOV = Math.PI / 2.2;        // vertical field of view

export default function PanoramaPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const pixelsRef = useRef<ImageData | null>(null);
  const [region, setRegion] = useState(REGIONS[0]);
  const [ready, setReady] = useState(false);
  const yaw = useRef(0), pitch = useRef(0);
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    setReady(false);
    const img = new Image();
    img.onload = () => {
      // Read the pixels once. Sampling an ImageData is vastly faster than drawImage per pixel.
      const c = document.createElement("canvas");
      c.width = img.width; c.height = img.height;
      const cx = c.getContext("2d");
      if (!cx) return;
      cx.drawImage(img, 0, 0);
      pixelsRef.current = cx.getImageData(0, 0, c.width, c.height);
      imgRef.current = img;
      setReady(true);
    };
    img.src = `/data/panoramas/${region.key}.png`;
  }, [region]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const src = pixelsRef.current;
    if (!canvas || !src) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const out = ctx.createImageData(W, H);
    const sw = src.width, sh = src.height, sd = src.data;
    const cy = Math.cos(pitch.current), sy = Math.sin(pitch.current);
    const cyaw = Math.cos(yaw.current), syaw = Math.sin(yaw.current);

    for (let y = 0; y < H; y++) {
      const v = (y / H - 0.5) * FOV;
      const cv = Math.cos(v), sv = Math.sin(v);
      for (let x = 0; x < W; x++) {
        const u = (x / W - 0.5) * FOV * (W / H);
        // ray in camera space
        let dx = Math.sin(u) * cv, dy = sv, dz = -Math.cos(u) * cv;
        // yaw, then pitch
        let x1 = dx * cyaw - dz * syaw, z1 = dx * syaw + dz * cyaw;
        let y2 = dy * cy - z1 * sy, z2 = dy * sy + z1 * cy;
        // equirectangular lookup: longitude from atan2, latitude from asin
        const lonA = Math.atan2(x1, -z2);
        const latA = Math.asin(Math.max(-1, Math.min(1, y2)));
        let sx = Math.floor(((lonA / (2 * Math.PI)) + 0.5) * sw);
        const sy2 = Math.floor((0.5 - latA / Math.PI) * sh);
        sx = ((sx % sw) + sw) % sw;
        const ty = Math.max(0, Math.min(sh - 1, sy2));
        const si = (ty * sw + sx) * 4, oi = (y * W + x) * 4;
        out.data[oi] = sd[si]; out.data[oi + 1] = sd[si + 1];
        out.data[oi + 2] = sd[si + 2]; out.data[oi + 3] = 255;
      }
    }
    ctx.putImageData(out, 0, 0);
  }, []);

  useEffect(() => { if (ready) draw(); }, [ready, draw]);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!drag.current) return;
      yaw.current -= (e.clientX - drag.current.x) * 0.0035;
      pitch.current = Math.max(-1.2, Math.min(1.2, pitch.current - (e.clientY - drag.current.y) * 0.0035));
      drag.current = { x: e.clientX, y: e.clientY };
      draw();
    };
    const onUp = () => { drag.current = null; };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") yaw.current += 0.12;
      else if (e.key === "ArrowRight") yaw.current -= 0.12;
      else if (e.key === "ArrowUp") pitch.current = Math.min(1.2, pitch.current + 0.08);
      else if (e.key === "ArrowDown") pitch.current = Math.max(-1.2, pitch.current - 0.08);
      else return;
      e.preventDefault();
      draw();
    };
    addEventListener("pointermove", onMove);
    addEventListener("pointerup", onUp);
    addEventListener("keydown", onKey);
    return () => {
      removeEventListener("pointermove", onMove);
      removeEventListener("pointerup", onUp);
      removeEventListener("keydown", onKey);
    };
  }, [draw]);

  return (
    <main style={{ padding: "1rem", maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: ".25rem" }}>Look around a valley</h1>
      <p style={{ opacity: .8, marginTop: 0 }}>
        Not a photograph. A 360-degree view rendered from the elevation grid this app already
        carries, so it works with the radio off. Drag to look around, or use the arrow keys.
      </p>

      <div style={{ display: "flex", gap: ".4rem", flexWrap: "wrap", margin: ".8rem 0" }}>
        {REGIONS.map((r) => (
          <button key={r.key} onClick={() => { setRegion(r); yaw.current = 0; pitch.current = 0; }}
                  style={{ padding: ".35rem .7rem", fontWeight: r.key === region.key ? 700 : 400,
                           opacity: r.key === region.key ? 1 : .65 }}>
            {r.name}
          </button>
        ))}
      </div>

      <canvas ref={canvasRef} width={W} height={H}
              onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY }; }}
              style={{ width: "100%", height: "auto", cursor: "grab", background: "#0b1220",
                       borderRadius: 8, touchAction: "none", display: "block" }} />

      <p style={{ opacity: .8, marginTop: ".6rem" }}>{region.note}</p>
      {!ready && <p>Loading {region.name}&hellip;</p>}

      <p style={{ opacity: .7, fontSize: ".9rem", marginTop: "1rem" }}>
        A silhouette from a roughly one-kilometre elevation grid: shape only, no trees, no buildings,
        and a gradient sky rather than a photograph. The horizon angles are measured, not styled -
        Kathmandu reads gentlest at 19 degrees and the Manaslu gorge steepest at 58, because that is
        how the ground is.
      </p>
    </main>
  );
}
