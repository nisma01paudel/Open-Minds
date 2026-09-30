"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SlopeMap, { AnyFC } from "../components/SlopeMap";
import Presenter from "../components/Presenter";

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

function apiBase(): string {
  // The flood planner is the one thing here that needs the field API. It is configurable with
  // ?api=http://host:port so the demo works against a laptop on any address, and it defaults to
  // the documented port rather than guessing.
  if (typeof window === "undefined") return "";
  const q = new URLSearchParams(window.location.search).get("api");
  return (q || "http://127.0.0.1:8080").replace(/\/+$/, "");
}

function speakNepali(text: string): "spoke" | "no-voice" | "unsupported" {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return "unsupported";
  const synth = window.speechSynthesis;
  const utterance = new SpeechSynthesisUtterance(text);
  const voices = synth.getVoices();
  const ne = voices.find((v) => (v.lang || "").toLowerCase().startsWith("ne"));
  // Read Nepali in a Nepali voice or not at all. A Devanagari instruction spoken by an English
  // voice is worse than silence: the listener hears confident nonsense.
  utterance.lang = ne ? ne.lang : "ne-NP";
  if (ne) utterance.voice = ne;
  utterance.rate = 0.95;
  synth.cancel();
  synth.speak(utterance);
  return ne ? "spoke" : "no-voice";
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
  const [adv, setAdv] = useState<any>(null);
  const [picked, setPicked] = useState<any>(null);
  const [blind, setBlind] = useState(false);
  const [flood, setFlood] = useState(false);
  const [esc, setEsc] = useState<any>(null);
  const [escErr, setEscErr] = useState("");
  const [escBusy, setEscBusy] = useState(false);
  const advisories = useRef<Record<string, any>>({});
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
      if (q.get("blind") === "1") setBlind(true);
    }).catch(() => setErr("timeline not built yet"));
    fetch("/data/observability-by-month.json").then((r) => r.json()).then(setObs).catch(() => {});
    fetch("/data/advisories.json").then((r) => r.json())
      .then((a) => {
        advisories.current = a.advisories ?? {};
        // ?adv=<site-id> opens a slope's advisory straight away, so a beat can be linked
        // and so the panel can be checked without clicking.
        const id = new URLSearchParams(location.search).get("adv");
        if (id && advisories.current[id]) {
          const v = advisories.current[id];
          setPicked({ id, title: v.title, r24: v.r24, state: "exceeded" });
          setAdv(v);
        }
      }).catch(() => {});
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
      <SlopeMap
        data={mode === "replay" ? replayFC : liveFC}
        focus={focus}
        blind={blind}
        onPick={(p, at) => {
          const a = advisories.current[p.id];
          setPicked(p);
          // advisories are precomputed for one day; only show them on that day
          setAdv(a && tl && tl.days[day] === "2024-09-28" ? a : null);

          // In flood mode the same click answers a different question: not "who is
          // responsible for this slope" but "which way do I run, and how high".
          if (!flood || !at) { setEsc(null); return; }
          setEsc(null);
          setEscErr("");
          setEscBusy(true);
          fetch(`${apiBase()}/api/v1/escape?lat=${at.lat}&lon=${at.lon}&rise_m=5`)
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
            .then((d) => { setEsc(d); if (d?.error) setEscErr(d.error); })
            .catch((e) => setEscErr(
              `${e.message} — is the field API running? ` +
              `python -m pahiro.api --port 8080`))
            .finally(() => setEscBusy(false));
        }}
      />

      {flood && (esc || escBusy || escErr) && (
        <aside className="advpanel escapepanel">
          <button className="advx" onClick={() => { setEsc(null); setEscErr(""); }}>✕</button>
          <h3>🌊 Where to run, and how high</h3>
          {escBusy && <p className="advlead">Working out the ground from the bundled DEM…</p>}
          {escErr && <p className="advlead" style={{ color: "#f59e0b" }}>{escErr}</p>}
          {esc && !esc.error && (
            <>
              {esc.reachable ? (
                <>
                  <div className="escbig">
                    GO <b>{String(esc.compass || "").toUpperCase()}</b>
                    {esc.distance_m != null && <> · about <b>{Math.round(esc.distance_m)} m</b></>}
                    {esc.climb_m != null && esc.climb_m > 1 && <> · climbing <b>{Math.round(esc.climb_m)} m</b></>}
                  </div>
                  <div className="advmeta">
                    {Math.round(esc.from_elevation_m)} m now → reach at least{" "}
                    {esc.target_elevation_m != null && Math.round(esc.target_elevation_m)} m
                    {esc.walk_minutes != null && <> · ~{Math.round(esc.walk_minutes)} min on foot</>}
                  </div>
                  <p className="advlead" style={{ fontSize: 17, lineHeight: 1.5 }}>
                    {esc.advice_ne}
                  </p>
                  <div className="escactions">
                    <button
                      className="escsp"
                      onClick={() => {
                        const r = speakNepali(esc.navigation?.spoken?.first_ne || esc.advice_ne);
                        if (r !== "spoke") {
                          setEscErr(r === "no-voice"
                            ? "No Nepali voice is installed on this device, so the instruction is shown rather than read badly in another language."
                            : "This browser has no speech synthesis.");
                        }
                      }}
                    >
                      🔊 सुन्नुहोस् — SPEAK IT
                    </button>
                    <button
                      className="escsp ghost"
                      onClick={() => speakNepali(esc.navigation?.spoken?.heading_ne || "")}
                    >
                      🔊 DIRECTION ONLY
                    </button>
                  </div>
                  <ol className="escsteps">
                    {(esc.navigation?.steps ?? []).map((s: any, i: number) => (
                      <li key={i}><b>{s.ne}</b><span className="dim"> — {s.en}</span></li>
                    ))}
                  </ol>
                </>
              ) : (
                <>
                  <div className="escbig warn">NO REACHABLE HIGH GROUND</div>
                  <p className="advlead" style={{ fontSize: 17, lineHeight: 1.5 }}>
                    {esc.advice_ne}
                  </p>
                  <div className="escactions">
                    <button className="escsp" onClick={() => speakNepali(esc.navigation?.spoken?.first_ne || esc.advice_ne)}>
                      🔊 सुन्नुहोस् — SPEAK IT
                    </button>
                  </div>
                </>
              )}
              <p className="advcaveat">
                <b>{esc.caveat}</b> Ground grid about {Math.round(esc.resolution_m)} m. This is
                terrain only — not turn-by-turn, and it cannot see the water.
              </p>
            </>
          )}
        </aside>
      )}

      {picked && (
        <aside className="advpanel">
          <button className="advx" onClick={() => { setPicked(null); setAdv(null); }}>✕</button>
          <h3>{adv?.title ?? picked.title ?? "Documented slope"}</h3>
          <div className="advmeta">
            {Math.round(picked.r24)} mm / 24 h · {picked.state}
          </div>
          {adv ? (
            <>
              <p className="advlead">
                <b>What the system would send.</b> Generated by the same code as the agent —
                advisory, responsible office, statute, and terrain recommendation.
              </p>
              <pre className="advtext">{adv.advisory_ne}</pre>
              <dl className="advkv">
                <dt>Responsible</dt><dd>{adv.authority ?? "—"}</dd>
                <dt>Office</dt><dd>{adv.office ?? "—"}</dd>
                <dt>Legal basis</dt><dd>{adv.legal_basis ?? "—"}</dd>
                {adv.siting && (
                  <>
                    <dt>Terrain</dt>
                    <dd>
                      {adv.siting.recommendation === "relocate-upslope"
                        ? `move ${Math.round(adv.siting.target_offset_m)} m upslope, +${Math.round(adv.siting.target_elevation_gain_m)} m`
                        : "repair in place"}
                    </dd>
                  </>
                )}
              </dl>
              <p className="advcaveat">
                {adv.siting?.caveat ??
                  "Terrain screening only; a geotechnical assessment is required before any design decision."}
              </p>
            </>
          ) : (
            <p className="advlead">
              No precomputed advisory for this slope on this date. Advisories are built for
              the 60 most loaded slopes of 2024-09-28 — open that day and click a red slope.
            </p>
          )}
        </aside>
      )}

      <header>
        <div className="brand">
          <h1>Pahiro Watch <span>पहिरो</span></h1>
          <p>Every documented landslide-prone slope in Nepal, each carrying the routing key&apos;s <b>default</b> duty holder for a local road — and the statute that says so.</p>
        </div>
      </header>

      <aside className="panel">
        <div className="frames">
          <button
            className={flood ? "flood on" : "flood"}
            aria-pressed={flood}
            onClick={() => {
              setFlood((f) => !f);
              setEsc(null); setEscErr("");
              if (flood) { setPicked(null); setAdv(null); }
            }}
            title="Answer 'which way do I run, and how high' for a clicked point"
          >
            🌊 FLASH FLOOD — WHERE DO I GO?
          </button>
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

        <label className="toggle">
          <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
          <span>
            Show <b>measured observability</b> — where the satellite could not see
          </span>
        </label>

        {blind && (
          <div className="blindnote">
            <b>142 real measurements.</b> Each point is a documented slope, in the month it
            failed, coloured by how much clear ground the satellite actually returned over
            30 days — red where nothing usable was seen, green where the ground was
            observable. In August only <b>16.8%</b> of scenes were usable; 17 of 142 sites
            had <b>none at all</b>.
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
          This is not detection. It is the list of slopes loaded on a given day, each carrying the
          routing key&apos;s default duty holder for a local road. Per-report routing, which resolves
          the actual asset, is measured separately on 21 expert-labelled scenarios.
        </div>
      </aside>

      <div className="topactions">
        <Link href="/fly/">🥽 Fly over it in 3D</Link>
        <Link href="/share/">Share the 10-second film</Link>
        <Link href="/ar/" className="phone">📱 Open the phone view — point it at a hillside</Link>
        {/* The other half of the project: what happens AFTER a slope fails. Warning is
            information; this is the thing someone holds while digging. */}
        <Link href="/field/" className="phone">🚨 Field app — SOS, the board, and the Bluetooth search</Link>
      </div>
      <Presenter
        beats={[
          { title: "1 · The national picture",
            cue: "Every documented landslide-prone slope in Nepal — 613 of them — on real Sentinel-2 imagery, each carrying the routing key's default duty holder for a local road, cited to the statute. Say 'default': per-report routing, which resolves the actual asset, is measured separately on 21 expert-labelled scenarios.",
            action: () => { setMode("live"); setPlaying(false); setFocus(null); } },
          { title: "2 · A quiet week",
            cue: "Mid-June. Not one slope above the threshold, and nothing approaching it. This is what the country looks like when it is not raining.",
            action: () => { setMode("replay"); setPlaying(false); setDay(tl ? tl.days.indexOf("2024-06-15") : 0); setFocus(null); } },
          { title: "3 · The season, running",
            cue: "Now the 2024 monsoon. Press play and watch the belt move.",
            action: () => { setMode("replay"); setDay(0); setSpeed(70); setPlaying(true); setFocus(null); } },
          { title: "4 · The day — 28 September 2024",
            cue: "305 of 613 slopes above the rainfall threshold on one day. That is the day Nepal recorded 167 landslides. Say clearly: this is not a forecast — we tested it, and the slopes that failed were not the most loaded.",
            action: () => { setMode("replay"); setPlaying(false); setDay(tl ? tl.days.indexOf("2024-09-28") : 0); setFocus(null); } },
          { title: "5 · And we could not see them",
            cue: "Here is the part that matters. In September only 27.8% of satellite imagery had clear ground. A slope can be loaded and invisible at the same time — which is the whole problem, and why the system says so instead of going quiet.",
            action: () => { setMode("replay"); setPlaying(false); setDay(tl ? tl.days.indexOf("2024-09-28") : 0); setFocus(null); } },
          { title: "5b · Where we are blind",
            cue: "Now the part no one else has measured. Each of these points is a documented slope, in the month it failed, coloured by how much clear ground the satellite actually returned. Red means it could not be seen at all. In August, only 16.8% of scenes were usable — and 17 of these slopes had nothing. This is the register nobody keeps.",
            action: () => { setMode("replay"); setPlaying(false); setBlind(true);
                            setDay(tl ? tl.days.indexOf("2024-08-15") : 0); setFocus(null); } },
          { title: "6 · Fly over it (3D)",
            cue: "Real elevation, real imagery, real rainfall. Press Enter to open the 3D view.",
            href: "/fly/", action: () => setBlind(false) },
          { title: "7 · From the phone",
            cue: "Now the part nobody else has. Point a phone at a hillside and it tells you that slope's state and who owns it. Press Enter.",
            href: "/ar/", action: () => setBlind(false) },
          { title: "8 · Leave them something",
            cue: "And the ten-second film, so the finding does not stay in this room. Press Enter.",
            href: "/share/", action: () => {} },
        ]}
      />
      <div className="hint">Drag to rotate · scroll to zoom · click a slope for the responsible office</div>
    </div>
  );
}
