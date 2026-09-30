"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SlopeMap, { AnyFC } from "../components/SlopeMap";

type Frame = { id: string; label: string; date: string; source: string; file: string;
               counts: Record<string, number>; worst_r24: number };
type Site = { id: string; title: string; lat: number; lon: number; authority?: string;
              office?: string; legal_basis?: string; r: (number | null)[] };
type Timeline = { start: string; end: string; days: string[]; source: string;
                  threshold_mm_24h: number; threshold_name: string; sites: Site[] };

// Mirrors pahiro.trigger: above the threshold, or within 20% of it.
const APPROACH = 0.8;

function dayFeatures(tl: Timeline, i: number, threshold: number): AnyFC {
  const day = tl.days[i];
  const feats: any[] = [];
  for (const s of tl.sites) {
    const v = s.r[i];
    if (v === null || v === undefined) continue;
    const state = v >= threshold ? "exceeded" : v >= threshold * APPROACH ? "approaching" : "below";
    feats.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [s.lon, s.lat] },
      properties: { id: s.id, title: s.title, state, r24: v, day,
                    authority: s.authority, office: s.office, legal_basis: s.legal_basis },
    });
  }
  return { type: "FeatureCollection", features: feats };
}

export default function Page() {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [tl, setTl] = useState<Timeline | null>(null);
  const [mode, setMode] = useState<"live" | "replay">("live");
  const [liveIdx, setLiveIdx] = useState(0);
  const [day, setDay] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(120); // ms per day
  const [err, setErr] = useState("");
  const raf = useRef<number | null>(null);

  useEffect(() => {
    fetch("/data/frames.json").then((r) => r.json()).then(setFrames)
      .catch(() => setErr("could not load frames.json"));
    fetch("/data/timeline.json").then((r) => r.json()).then((t: Timeline) => {
      setTl(t);
      const sep28 = t.days.indexOf("2024-09-28");
      setDay(sep28 >= 0 ? sep28 : 0);
    }).catch(() => setErr("timeline not built yet"));
  }, []);

  const threshold = tl?.threshold_mm_24h ?? 118.8;

  // National pulse: how many slopes are above threshold each day. Cheap to compute once
  // and it is the thing that tells you where the monsoon actually struck.
  const pulse = useMemo(() => {
    if (!tl) return [] as number[];
    return tl.days.map((_, i) => {
      let n = 0;
      for (const s of tl.sites) { const v = s.r[i]; if (v !== null && v !== undefined && v >= threshold) n++; }
      return n;
    });
  }, [tl, threshold]);
  const peak = useMemo(() => pulse.reduce((a, b, i) => (b > pulse[a] ? i : a), 0), [pulse]);

  const liveData = useMemo<AnyFC | null>(() => {
    if (mode !== "live" || !frames.length) return null;
    return null; // filled by the effect below via the file fetch
  }, [mode, frames]);

  const [liveFC, setLiveFC] = useState<AnyFC | null>(null);
  useEffect(() => {
    if (mode !== "live" || !frames[liveIdx]) return;
    fetch(`/data/${frames[liveIdx].file}`).then((r) => r.json()).then(setLiveFC).catch(() => {});
  }, [mode, liveIdx, frames]);

  const replayFC = useMemo(
    () => (mode === "replay" && tl ? dayFeatures(tl, day, threshold) : null),
    [mode, tl, day, threshold],
  );

  // ---- playback ----
  const tick = useCallback(() => {
    setDay((d) => {
      if (!tl) return d;
      if (d >= tl.days.length - 1) { setPlaying(false); return d; }
      return d + 1;
    });
  }, [tl]);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(tick, speed);
    return () => clearInterval(t);
  }, [playing, speed, tick]);

  const counts = useMemo(() => {
    const fc = mode === "replay" ? replayFC : liveFC;
    let ex = 0, ap = 0, tot = 0, worst = 0;
    for (const f of fc?.features ?? []) {
      const p = f.properties;
      tot++; worst = Math.max(worst, p.r24);
      if (p.state === "exceeded") ex++; else if (p.state === "approaching") ap++;
    }
    return { ex, ap, tot, worst };
  }, [replayFC, liveFC, mode]);

  const label = mode === "replay" ? tl?.days[day] ?? "—" : frames[liveIdx]?.date ?? "—";

  return (
    <div className="stage">
      <SlopeMap data={mode === "replay" ? replayFC : liveFC} />

      <header>
        <div className="brand">
          <h1>Pahiro Watch <span>पहिरो</span></h1>
          <p>Every documented landslide-prone slope in Nepal, with the office legally responsible for each.</p>
        </div>
      </header>

      <aside className="panel">
        <div className="frames">
          <button aria-pressed={mode === "live"} onClick={() => { setMode("live"); setPlaying(false); }}>
            Live · {frames[0]?.date ?? "—"}
          </button>
          <button aria-pressed={mode === "replay"} onClick={() => setMode("replay")}>
            Monsoon 2024 {tl ? `· ${tl.days.length} days` : ""}
          </button>
        </div>

        {err && <div style={{ color: "#f59e0b", fontSize: 12.5 }}>{err}</div>}

        <div className="statgrid">
          <div className="stat"><b style={{ color: "var(--exceeded)" }}>{counts.ex}</b><span>above threshold</span></div>
          <div className="stat"><b style={{ color: "var(--approaching)" }}>{counts.ap}</b><span>approaching</span></div>
          <div className="stat"><b>{counts.tot}</b><span>slopes mapped</span></div>
          <div className="stat"><b>{Math.round(counts.worst)}<small style={{ fontSize: 14 }}> mm</small></b><span>worst 24 h</span></div>
        </div>

        {mode === "replay" && tl && (
          <div className="replay">
            <div className="replaybar">
              <button className="play" onClick={() => setPlaying((p) => !p)}>
                {playing ? "❚❚" : "▶"}
              </button>
              <b className="date">{label}</b>
              <button className="mini" onClick={() => setSpeed((s) => (s === 240 ? 60 : s === 60 ? 120 : 240))}>
                {speed === 240 ? "1×" : speed === 120 ? "2×" : "4×"}
              </button>
            </div>
            <input
              type="range" min={0} max={tl.days.length - 1} value={day}
              onChange={(e) => { setPlaying(false); setDay(Number(e.target.value)); }}
            />
            <div className="pulse" title={`National pulse — peak ${pulse[peak]} slopes on ${tl.days[peak]}`}>
              {pulse.map((n, i) => (
                <span key={i}
                  className={"bar" + (i === day ? " at" : "")}
                  style={{ height: `${Math.max(2, (n / Math.max(1, pulse[peak])) * 100)}%` }}
                  onClick={() => { setPlaying(false); setDay(i); }} />
              ))}
            </div>
            <div className="pulselabel">
              national pulse · peak <b>{pulse[peak]}</b> slopes on <b>{tl.days[peak]}</b>
              <button className="mini" onClick={() => { setPlaying(false); setDay(peak); }}>jump to peak</button>
            </div>
          </div>
        )}

        <div className="legend">
          <div><i className="swatch" style={{ background: "var(--exceeded)" }} /> Above the threshold — inspect</div>
          <div><i className="swatch" style={{ background: "var(--approaching)" }} /> Approaching the threshold</div>
          <div><i className="swatch" style={{ background: "var(--below)" }} /> Below the threshold</div>
        </div>

        <div className="foot">
          {mode === "replay"
            ? <>Rainfall: CHIRPS 0.05° daily over {(tl?.days.length ?? 0)} days of the 2024 monsoon.
                Threshold: the published Panchpokhari Thangpal curve, 118.8 mm/24 h — a <b>local</b> fit
                used as a national reference.</>
            : <>Rainfall: Open-Meteo (near-real-time). Threshold: 118.8 mm/24 h, as above.</>}
          <br /><br />
          This is not detection. It is the list of slopes loaded on a given day, and who is on the
          hook for each.
        </div>
      </aside>

      <Link href="/ar/" className="phone">📱 Open the phone view — point it at a hillside</Link>
      <div className="hint">Drag to rotate · scroll to zoom · click a slope for the responsible office</div>
    </div>
  );
}
