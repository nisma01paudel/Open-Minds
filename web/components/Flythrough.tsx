"use client";

import { useEffect, useRef, useState } from "react";

type TerrainMeta = {
  width: number; height: number; west: number; south: number; east: number; north: number;
  min_m: number; max_m: number;
};
type Site = { id: string; title: string; lat: number; lon: number;
              authority?: string; legal_basis?: string; r: (number | null)[] };
type Timeline = { days: string[]; threshold_mm_24h: number; sites: Site[] };

const WINDOWS: [number, number][] = [[24, 118.8], [48, 141.9], [72, 157.5]];
const EXCEEDED = 0, APPROACH = 1, BELOW = 2;

function stateFor(r: (number | null)[], i: number): number {
  if (r[i] === null || r[i] === undefined) return BELOW;
  const back: number[] = [];
  for (const k of [0, 1, 2]) {
    const x = i - k >= 0 ? r[i - k] : null;
    if (x !== null && x !== undefined) back.push(x);
  }
  const sums = [back[0], back.length >= 2 ? back[0] + back[1] : null,
                back.length >= 2 ? back[0] + back[1] + (back[2] ?? 0) : null];
  let best = 0;
  for (let w = 0; w < 3; w++) if (sums[w] !== null) best = Math.max(best, sums[w] / WINDOWS[w][1]);
  return best >= 1 ? EXCEEDED : best >= 0.8 ? APPROACH : BELOW;
}

/** Real elevation, real satellite imagery, real rainfall. Nothing here is invented. */
export default function Flythrough() {
  const holder = useRef<HTMLDivElement>(null);
  const three = useRef<any>(null);
  const [tl, setTl] = useState<Timeline | null>(null);
  const [meta, setMeta] = useState<TerrainMeta | null>(null);
  const [day, setDay] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [flying, setFlying] = useState(true);
  const [counts, setCounts] = useState({ ex: 0, ap: 0 });
  const [xrOk, setXrOk] = useState(false);
  const [status, setStatus] = useState("loading terrain…");

  const api = useRef<any>({ setDay: () => {}, setFly: () => {}, vr: () => {} });
  const dayRef = useRef(0);

  useEffect(() => {
    fetch("/data/timeline.json").then((r) => r.json()).then((t) => {
      setTl(t);
      const s28 = t.days.indexOf("2024-09-28");
      const d = s28 >= 0 ? s28 : 0;
      setDay(d);
      api.current.setDay?.(d);
    });
    fetch("/data/terrain.json").then((r) => r.json()).then(setMeta);
    if ((navigator as any).xr?.isSessionSupported) {
      (navigator as any).xr.isSessionSupported("immersive-vr").then((ok: boolean) => setXrOk(ok));
    }
  }, []);

  // ---- build the scene once the terrain is here ----
  useEffect(() => {
    if (!meta) return;
    let stop = false;
    let raf = 0;

    (async () => {
     try {
      const THREE = await import("three");
      const OrbitControls = (await import("three/examples/jsm/controls/OrbitControls.js")).OrbitControls;
      if (stop || !holder.current) return;

      const W = meta.east - meta.west, H = meta.north - meta.south;
      const PLANE_W = W * 100, PLANE_H = H * 100;   // 1 unit ~ 1 km
      const V = 12;                                  // vertical exaggeration
      // Mesh density. 2 is the shipping detail; the software GL used for automated
      // screenshots cannot render it in reasonable time, so it is overridable for
      // verification. On a real GPU, 2 is comfortable.
      const step = Math.max(1, Number(new URLSearchParams(location.search).get("step")) || 2);

      const buf = await (await fetch("/data/terrain.bin")).arrayBuffer();
      const all = new Int16Array(buf);
      const gw = meta.width, gh = meta.height;
      const rw = Math.floor(gw / step), rh = Math.floor(gh / step);

      const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.setSize(holder.current.clientWidth, holder.current.clientHeight);
      renderer.xr.enabled = true;
      holder.current.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x05070d);
      scene.fog = new THREE.Fog(0x0a1020, PLANE_W * 1.1, PLANE_W * 2.6);

      const camera = new THREE.PerspectiveCamera(
        55, holder.current.clientWidth / holder.current.clientHeight, 0.5, PLANE_W * 8);
      camera.position.set(-PLANE_W * 0.34, 330, PLANE_H * 0.92);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.06;
      controls.target.set(PLANE_W * 0.02, 18, -PLANE_H * 0.06);
      controls.maxPolarAngle = Math.PI * 0.49;
      controls.minDistance = 40;
      controls.maxDistance = PLANE_W * 1.6;

      // terrain mesh
      const geo = new THREE.PlaneGeometry(PLANE_W, PLANE_H, rw - 1, rh - 1);
      geo.rotateX(-Math.PI / 2);
      const pos = geo.attributes.position as any;
      const hAt = (row: number, col: number) =>
        all[Math.min(gh - 1, row * step) * gw + Math.min(gw - 1, col * step)];

      for (let r = 0; r < rh; r++) {
        for (let c = 0; c < rw; c++) {
          const i = r * rw + c;
          const e = hAt(r, c);
          pos.setY(i, Math.max(0, e) / 1000 * V);   // metres -> km -> exaggerated
        }
      }
      geo.computeVertexNormals();

      const tex = await new Promise<any>((res) => {
        new THREE.TextureLoader().load("/data/terrain-texture.jpg", (t: any) => {
          t.colorSpace = THREE.SRGBColorSpace;
          res(t);
        }, undefined, () => res(null));
      });

      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
        map: tex ?? undefined,
        roughness: 0.94, metalness: 0.02,
        color: tex ? 0xffffff : 0x4b5563,
      }));
      scene.add(mesh);

      scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x1b2436, 0.85));
      const sun = new THREE.DirectionalLight(0xfff3e0, 1.5);
      sun.position.set(-PLANE_W * 0.5, 260, -PLANE_H * 0.4);
      scene.add(sun);

      setStatus("");

      // one round sprite shared by both point passes - square points looked like blocks
      const disc = (() => {
        const c = document.createElement("canvas");
        c.width = c.height = 64;
        const g = c.getContext("2d")!;
        const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
        grd.addColorStop(0.0, "rgba(255,255,255,1)");
        grd.addColorStop(0.45, "rgba(255,255,255,0.95)");
        grd.addColorStop(0.72, "rgba(255,255,255,0.35)");
        grd.addColorStop(1.0, "rgba(255,255,255,0)");
        g.fillStyle = grd;
        g.fillRect(0, 0, 64, 64);
        return new THREE.CanvasTexture(c);
      })();
      // slope markers
      const makePoints = (sites: Site[]) => {
        const g = new THREE.BufferGeometry();
        const n = sites.length;
        const verts = new Float32Array(n * 3);
        const cols = new Float32Array(n * 3);
        const idx: number[] = [];
        sites.forEach((s, i) => {
          const x = ((s.lon - meta.west) / W - 0.5) * PLANE_W;
          const z = -( (s.lat - meta.south) / H - 0.5) * PLANE_H;
          const col = Math.round(((s.lon - meta.west) / W) * (gw - 1));
          const row = Math.round((1 - (s.lat - meta.south) / H) * (gh - 1));
          const e = all[Math.min(gh - 1, Math.max(0, row)) * gw + Math.min(gw - 1, Math.max(0, col))];
          verts[i * 3] = x;
          verts[i * 3 + 1] = Math.max(0, e) / 1000 * V + 2.2;
          verts[i * 3 + 2] = z;
        });
        g.setAttribute("position", new THREE.BufferAttribute(verts, 3));
        g.setAttribute("color", new THREE.BufferAttribute(cols, 3));
        const m = new THREE.PointsMaterial({
          map: disc, alphaTest: 0.04, depthWrite: false,
          size: 15, vertexColors: true, sizeAttenuation: true,
          transparent: true, opacity: 0.98,
        });
        return { geo: g, mat: m, idx };
      };

      let sitesRef: Site[] = [];
      let pts: any = null;
      let curDay = -1;

      const paint = (d: number) => {
        if (!pts || !sitesRef.length) return;
        // makePoints() returns { geo, mat } — reading `pts.geometry` here threw at runtime
        // and took the whole 3D view down with a blank canvas.
        const cols = pts.geo.attributes.color as any;
        let ex = 0, ap = 0;
        sitesRef.forEach((s, i) => {
          const st = stateFor(s.r, d);
          if (st === EXCEEDED) ex++; else if (st === APPROACH) ap++;
          const c = st === EXCEEDED ? [1.0, 0.16, 0.11]
                  : st === APPROACH ? [1.0, 0.62, 0.04]
                  : [0.55, 0.63, 0.72];
          cols.setXYZ(i, c[0], c[1], c[2]);
        });
        cols.needsUpdate = true;
        setCounts({ ex, ap });
        curDay = d;
      };

      // Guard on the sites, NOT on `tl`. The scene is built when the terrain arrives,
      // which is usually before the timeline does, so a closure over `tl` captured null
      // and this returned immediately on every call - the date advanced and the colours
      // and counts never moved.
      api.current.setDay = (d: number) => { if (sitesRef.length && d !== curDay) paint(d); };
      api.current.setFly = (on: boolean) => setFlying(on);
      api.current.vr = async () => {
        try {
          const session = await (navigator as any).xr.requestSession("immersive-vr", {
            optionalFeatures: ["local-floor", "bounded-floor"],
          });
          await renderer.xr.setSession(session);
        } catch (e) { console.warn("[pahiro] vr:", e); }
      };

      setTl((t) => {
        if (!t) return t;
        sitesRef = t.sites;
        pts = makePoints(t.sites);
        scene.add(new THREE.Points(pts.geo, pts.mat));
        // a second, larger, softer pass so the loaded slopes read at distance
        const glow = new THREE.Points(pts.geo, new THREE.PointsMaterial({
          map: disc, size: 40, vertexColors: true, transparent: true, opacity: 0.30,
          depthWrite: false, alphaTest: 0.02, blending: THREE.AdditiveBlending,
        }));
        scene.add(glow);
        paint(dayRef.current);          // whatever day it is NOW, not when we started
        return t;
      });

      // ---- animate ----
      const t0 = performance.now();
      const renderLoop = () => {
        if (flying) {
          const t = ((performance.now() - t0) / 1000) * 0.035;
          const a = Math.sin(t), b = Math.cos(t);
          camera.position.set(a * PLANE_W * 0.40, 300 + 110 * b, PLANE_H * 0.62 + 120 * b);
          controls.target.set(a * PLANE_W * 0.26, 22 + 30 * b, -PLANE_H * 0.12);
        }
        controls.update();
        renderer.render(scene, camera);
      };
      renderer.setAnimationLoop(renderLoop);

      const onResize = () => {
        if (!holder.current) return;
        camera.aspect = holder.current.clientWidth / holder.current.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(holder.current.clientWidth, holder.current.clientHeight);
      };
      addEventListener("resize", onResize);

      three.current = { renderer, scene, camera, controls };
     } catch (e: any) {
       // Never fail silently - a blank 3D view looked like a design choice once already.
       console.error("[pahiro] flythrough:", e);
       setStatus(`3D failed: ${e?.message ?? e}`);
     }
    })();

    return () => {
      stop = true;
      cancelAnimationFrame(raf);
      const t = three.current;
      if (t) {
        t.renderer.setAnimationLoop(null);
        t.renderer.dispose();
        t.renderer.domElement?.remove();
      }
      three.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  // The single place that drives the scene. Doing this inside a setState updater instead
  // was a side effect in a pure function: the date advanced but the colours and counts
  // stayed frozen on the first frame.
  useEffect(() => { dayRef.current = day; api.current.setDay?.(day); }, [day]);

  useEffect(() => {
    if (!playing || !tl) return;
    const id = setInterval(() => {
      setDay((d) => (d >= tl.days.length - 1 ? 0 : d + 1));
    }, 130);
    return () => clearInterval(id);
  }, [playing, tl]);

  return (
    <div className="flystage">
      <div id="fly" ref={holder} />
      {status && <div className="flyhint">{status}</div>}

      <header>
        <div className="brand">
          <h1>Pahiro <span>3D</span></h1>
          <p>Real elevation, real satellite imagery, real rainfall — the 2024 monsoon over Nepal.</p>
        </div>
      </header>

      <aside className="flypanel">
        <div className="flydate">{tl?.days[day] ?? "—"}</div>
        <div className="flycounts">
          <div><b style={{ color: "var(--exceeded)" }}>{counts.ex}</b><span>above</span></div>
          <div><b style={{ color: "var(--approaching)" }}>{counts.ap}</b><span>approaching</span></div>
        </div>
        <input type="range" min={0} max={Math.max(0, (tl?.days.length ?? 1) - 1)} value={day}
               onChange={(e) => { const v = Number(e.target.value); setPlaying(false); setDay(v); api.current.setDay?.(v); }} />
        <div className="flyrow">
          <button onClick={() => setPlaying((p) => !p)}>{playing ? "❚❚ pause" : "▶ play season"}</button>
          <button onClick={() => { const v = !flying; setFlying(v); api.current.setFly?.(v); }}>
            {flying ? "✋ manual camera" : "🎬 auto fly"}
          </button>
          {xrOk && <button className="vr" onClick={() => api.current.vr?.()}>🥽 enter VR</button>}
        </div>
        <div className="flyfoot">
          Elevation: AWS Terrain Tiles · Imagery: Esri World Imagery · Rainfall: CHIRPS.
          Vertical scale exaggerated {12}× — real relief is about 1% of Nepal&apos;s width.
          The threshold is a published <b>local</b> fit used as a national reference.
        </div>
      </aside>
    </div>
  );
}
