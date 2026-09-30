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
type Obs = { sites: number; months: Record<string, { name: string; scenes: number;
             usable: number; pct: number }> };

// Mirrors pahiro.trigger exactly: a slope counts as loaded if ANY intensity-duration
// window crosses its own threshold, not just the 24-hour one.
//
// This is not a detail. On 2024-09-28 the single-day rule gives 31 slopes; the
// multi-window rule gives 305 - and 305 is what the agent itself reports. Using the day
// value alone under-counted the country by ten times and made the map disagree with the
// system it is supposed to be showing.
const APPROACH = 0.8;
const WINDOWS: [number, number][] = [[24, 118.8], [48, 141.9], [72, 157.5]];

function stateFor(r: (number | null)[], i: number): { state: string; r24: number } | null {
  const v = r[i];
  if (v === null || v === undefined) return null;
  const back: number[] = [];
  for (const k of [0, 1, 2]) {
    const x = i - k >= 0 ? r[i - k] : null;
    if (x !== null && x !== undefined) back.push(x);
  }
  const sums = [back[0], back.length >= 2 ? back[0] + back[1] : null,
                back.length >= 2 ? back[0] + back[1] + (back[2] ?? 0) : null];
  let best = 0;      // highest fraction of any window's threshold
  for (let w = 0; w < WINDOWS.length; w++) {
    const sum = sums[w];
    if (sum === null) continue;
    best = Math.max(best, sum / WINDOWS[w][1]);
  }
  const state = best >= 1 ? "exceeded" : best >= APPROACH ? "approaching" : "below";
  return { state, r24: v };
}

function dayFeatures(tl: Timeline, i: number, _threshold: number): AnyFC {
  const day = tl.days[i];
  const feats: any[] = [];
  for (const s of tl.sites) {
    const got = stateFor(s.r, i);
    if (!got) continue;
    feats.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [s.lon, s.lat] },
      properties: { id: s.id, title: s.title, state: got.state, r24: got.r24, day,
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
  const [obs, setObs] = useState<Obs | null>(null);
  const [focus, setFocus] = useState<{ lon: number; lat: number; zoom?: number } | null>(null);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    fetch("/data/frames.json").then((r) => r.json()).then(setFrames)
      .catch(() => setErr("could not load frames.json"));
    fetch("/data/timeline.json").then((r) => r.json()).then((t: Timeline) => {
      setTl(t);
      // ?mode=replay&day=119  or  ?mode=replay&on=2024-09-28 - so any moment in the
      // season can be linked, screenshotted, or put on a slide.
      const q = new URLSearchParams(location.search);
      const on = q.get("on");
      const idx = on ? t.days.indexOf(on) : Number(q.get("day"));
      setDay(Number.isFinite(idx) && idx >= 0 ? idx : Math.max(0, t.days.indexOf("2024-09-28")));
      if (q.get("mode") === "replay") setMode("replay");
    }).catch(() => setErr("timeline not built yet"));
    fetch("/data/observability-by-month.json").then((r) => r.json()).then(setObs).catch(() => {});
  }, []);

  const threshold = tl?.threshold_mm_24h ?? 118.8;

  // National pulse: how many slopes are above threshold each day. Cheap to compute once
  // and it is the thing that tells you where the monsoon actually struck.
  const pulse = useMemo(() => {
    if (!tl) return [] as number[];
    return tl.days.map((_, i) => {
      let n = 0;
      for (const s of tl.sites) if (stateFor(s.r, i)?.state === "exceeded") n++;
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

  const worst = useMemo(() => {
    if (!tl) return null;
    let best: Site | null = null; let bestV = -1;
    for (const s of tl.sites) {
      const v = s.r[day];
      if (v !== null && v !== undefined && v > bestV) { bestV = v; best = s; }
    }
    return best ? { site: best, mm: bestV } : null;
  }, [tl, day]);

  const monthKey = mode === "replay" && tl ? tl.days[day]?.slice(5, 7) : null;
  const monthObs = monthKey ? obs?.months?.[monthKey] : null;

  const label = mode === "replay" ? tl?.days[day] ?? "—" : frames[liveIdx]?.date ?? "—";

  return (
    <div className="stage">
      <SlopeMap data={mode === "replay" ? replayFC : liveFC} focus={focus} />

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
          <button
            className="present"
            onClick={() => { setMode("replay"); setDay(0); setSpeed(70); setPlaying(true); }}
            title="Play the whole season from the start"
          >
            ▶ Present
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
                  className={"bar" + (i === day ? " at" : "") + (n > 0 ? " has" : "")}
                  title={`${tl.days[i]} — ${n} above threshold`}
                  style={{ height: `${Math.max(4, Math.sqrt(n / Math.max(1, pulse[peak])) * 100)}%` }}
                  onClick={() => { setPlaying(false); setDay(i); }} />
              ))}
            </div>
            <div className="pulselabel">
              <span>national pulse · peak <b>{pulse[peak]}</b> on <b>{tl.days[peak]}</b>
                {" · "}{pulse.filter((n) => n > 0).length} of {pulse.length} days had any slope loaded</span>
              <button className="mini" onClick={() => { setPlaying(false); setDay(peak); }}>peak</button>
            </div>

            {worst && (
              <div className="worstline">
                worst today: <b>{worst.site.title || "slope"}</b> · {Math.round(worst.mm)} mm
                <button className="mini"
                  onClick={() => setFocus({ lon: worst.site.lon, lat: worst.site.lat })}>
                  fly there
                </button>
              </div>
            )}

            {monthObs && (
              <div className="blind">
                <b>{monthObs.name}: only {monthObs.pct}% of satellite scenes were usable</b>
                <span>
                  {monthObs.usable.toLocaleString()} of {monthObs.scenes.toLocaleString()} scenes
                  had clear ground, measured at {obs?.sites} documented sites. A slope can be
                  loaded and invisible at the same time — which is the whole problem.
                </span>
              </div>
            )}
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

      <div className="topactions">
        <Link href="/share/">Share the 10-second film</Link>
        <Link href="/ar/" className="phone">📱 Open the phone view — point it at a hillside</Link>
      </div>
      <div className="hint">Drag to rotate · scroll to zoom · click a slope for the responsible office</div>
    </div>
  );
}
