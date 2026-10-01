"use client";

import { dataUrl } from "../lib/base";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SlopeMap, { AnyFC } from "../components/SlopeMap";
import Provenance from "../components/Provenance";
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
  // Every optional data layer records its own failure here instead of vanishing. A layer that fails
  // to load and a layer with nothing to show are the same screen, and this product's argument is
  // that a user must be able to tell "nothing is here" from "we could not look" - which has to hold
  // for the app's own furniture, not only for the map data.
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const noteLoadFailure = (what: string) =>
    setLoadErrors((prev) => (prev.includes(what) ? prev : [...prev, what]));
  const [focus, setFocus] = useState<{ lon: number; lat: number; zoom?: number } | null>(null);
  const [adv, setAdv] = useState<any>(null);
  const [picked, setPicked] = useState<any>(null);
  const [blind, setBlind] = useState(false);
  const [trails, setTrails] = useState(false);
  const [places, setPlaces] = useState(false);
  // Planning a walk. The engine is Python and this page is a static export, so this talks to the
  // local API. When the API is not running the panel says so instead of silently doing nothing.
  const [planQ, setPlanQ] = useState("");
  const [planOut, setPlanOut] = useState<any>(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [planErr, setPlanErr] = useState("");
  // A walk that can be linked to. ?adv=<site-id> already opens an advisory directly so a beat
  // can be linked and the panel checked without clicking; the planner had no equivalent, which
  // made it the one feature that could not be shown or verified from a URL.
  const [autoPlan, setAutoPlan] = useState<string | null>(null);

  const runPlan = useCallback(async (override?: string) => {
    const q = (override ?? planQ).trim();
    if (!q) return;
    setPlanBusy(true); setPlanErr(""); setPlanOut(null);
    try {
      // Plan from wherever the map is looking, falling back to Kathmandu.
      const c = focus ?? { lat: 27.7047, lon: 85.3146 };
      const r = await fetch(
        `${apiBase()}/api/v1/plan?q=${encodeURIComponent(q)}&lat=${c.lat}&lon=${c.lon}`);
      const body = await r.json();
      if (body.error) setPlanErr(body.error);
      else setPlanOut(body);
    } catch (e: any) {
      setPlanErr(String(e?.message ?? e));
    } finally {
      setPlanBusy(false);
    }
  }, [planQ, focus, apiBase]);

  // ?plan=<sentence> asks the question on load, so a walk can be linked to the way an advisory can
  // with ?adv=. It runs once: autoPlan is cleared as it is consumed, so a later edit of the text box
  // does not re-fire the URL's request.
  useEffect(() => {
    if (!autoPlan) return;
    const text = autoPlan;
    setAutoPlan(null);
    setPlanQ(text);
    void runPlan(text);
  }, [autoPlan, runPlan]);
  const [flood, setFlood] = useState(false);
  const [esc, setEsc] = useState<any>(null);
  const [escErr, setEscErr] = useState("");
  const [escBusy, setEscBusy] = useState(false);
  const advisories = useRef<Record<string, any>>({});
  const raf = useRef<number | null>(null);

  useEffect(() => {
    fetch(dataUrl("/data/frames.json")).then((r) => r.json()).then(setFrames)
      .catch(() => setErr("could not load frames.json"));
    fetch(dataUrl("/data/timeline.json")).then((r) => r.json()).then((t: Timeline) => {
      setTl(t);
      // ?mode=replay&day=119  or  ?mode=replay&on=2024-09-28 - so any moment in the
      // season can be linked, screenshotted, or put on a slide.
      const q = new URLSearchParams(location.search);
      const on = q.get("on");
      const idx = on ? t.days.indexOf(on) : Number(q.get("day"));
      setDay(Number.isFinite(idx) && idx >= 0 ? idx : Math.max(0, t.days.indexOf("2024-09-28")));
      if (q.get("mode") === "replay") setMode("replay");
      if (q.get("blind") === "1") setBlind(true);
      if (q.get("trails") === "1") setTrails(true);
      // blind and trails each had a URL parameter; places did not, so the one layer a person
      // most wants to link to - where the local units are - could only be turned on by clicking.
      if (q.get("places") === "1") setPlaces(true);
      const pv = q.get("plan");
      if (pv) setAutoPlan(pv);
    }).catch(() => setErr("timeline not built yet"));
    fetch(dataUrl("/data/observability-by-month.json"))
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setObs)
      .catch(() => noteLoadFailure("the observability layer"));
    fetch(dataUrl("/data/advisories.json")).then((r) => r.json())
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
      })
      .catch(() => noteLoadFailure("the slope advisories"));
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
    fetch(dataUrl(`/data/${frames[liveIdx].file}`))
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setLiveFC)
      .catch(() => noteLoadFailure("this day's slope layer"));
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
      {loadErrors.length > 0 && (
        <div className="loaderrors" role="status"
             title="These sections could not be loaded, so what you see is incomplete.">
          Could not load {loadErrors.join(", ")} — what you see is incomplete.
        </div>
      )}
            <Provenance />
<SlopeMap
        data={mode === "replay" ? replayFC : liveFC}
        focus={focus}
        blind={blind}
        trails={trails}
        places={places}
        onLoadError={noteLoadFailure}
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

      {/* Shown only below 900px, where the panel itself is display:none. Without it a request for
          ?adv on a narrow window produced no advisory and no reason - a silent hide. Its own
          conditional, because the block below expects a single element. */}
      {picked && (
        <div className="advnarrow" role="status">
          The advisory for this slope is shown on a wider window (over 900 px), or in the field app,
          which carries it offline. Nothing has been hidden except the space to print it.
        </div>
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

        <div className="planbox">
          <div className="planhead">
            <b>Plan a walk</b>
            <span>Ask in your own words — the open-weight model reads it, the engine decides.</span>
          </div>
          <div className="planrow">
            <input
              type="text"
              value={planQ}
              placeholder="easy half day walk, a view, bus under Rs 40"
              onChange={(e) => setPlanQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") runPlan(); }}
            />
            <button className="act" disabled={planBusy || !planQ.trim()} onClick={() => runPlan()}>
              {planBusy ? "planning…" : "Plan"}
            </button>
          </div>
          {["easy walk with a view", "a hard 6 hour climb under Rs 60", "short morning walk"]
            .map((ex) => (
              <button key={ex} className="chip" onClick={() => { setPlanQ(ex); }}>
                {ex}
              </button>
            ))}

          {planErr && (
            <div className="planerr">
              <b>Could not reach the planner.</b> {planErr}
              <div style={{ marginTop: 6, opacity: 0.8 }}>
                The trail engine runs locally: start it with <code>python -m pahiro.api</code> (or
                <code> ./scripts/demo.sh</code>). The map, the trails and everything else on this
                page work without it.
              </div>
            </div>
          )}

          {planOut && !planErr && (
            <div className="planout">
              <div className="planunderstood">
                understood as <b>{planOut.understood}</b>
                <span className="plansrc">
                  {planOut.understood_by}.{" "}
                  {planOut.understood_by.startsWith("keyword")
                    ? "Start the model server for a better reading; the plan is the same engine either way."
                    : "Its output is validated before the engine uses it."}
                </span>
                {planOut.refused_fields?.length > 0 && (
                  <div style={{ marginTop: 4, opacity: 0.8 }}>
                    ignored from the model: {planOut.refused_fields.join(", ")}
                  </div>
                )}
              </div>
              {planOut.options?.length === 0 && (
                <div className="plainnote">
                  Nothing matched. Loosen the request — or note that Nepali footpath data is
                  incomplete, so a missing trail is one nobody has drawn yet.
                </div>
              )}
              {planOut.options?.map((o: any, i: number) => (
                <div className="planopt" key={i}>
                  <div className="planoptname">{o.name}</div>
                  <div className="planoptmeta">
                    {(o.length_m / 1000).toFixed(1)} km · +{o.climb_m} m ·{" "}
                    {Math.floor(o.minutes / 60)}h{String(o.minutes % 60).padStart(2, "0")} ·{" "}
                    {o.difficulty}
                  </div>
                  {o.bus && (
                    <div className="planbus">
                      🚌 {o.bus.stop} — about <b>Rs {o.bus.fare_rs}</b>
                      {o.bus.walk_from_stop_m > 200
                        ? `, then ${(o.bus.walk_from_stop_m / 1000).toFixed(1)} km on foot`
                        : ", trailhead at the stop"}
                    </div>
                  )}
                  <div className="planfits">{o.fits.join(" · ")}</div>
                </div>
              ))}
              <div className="plainnote">{planOut.caveats?.join(" ")}</div>
            </div>
          )}
        </div>

        <label className="toggle">
          <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
          <span>
            Show <b>measured observability</b> — where the satellite could not see
          </span>
        </label>

        <label className="toggle">
          <input type="checkbox" checked={trails} onChange={(e) => setTrails(e.target.checked)} />
          <span>
            Show <b>hiking trails</b> — 23,726 mapped paths, offline
          </span>
        </label>

        {/* This was JSX inside the .then() callback that loads the timeline - an expression
            evaluated and discarded, never returned. The layer, the source and the fetch were all
            written; the control to switch it on rendered nowhere, so the major-places layer was
            unreachable from the interface for every round it existed. */}
        <label className="toggle">
          <input type="checkbox" checked={places} onChange={(e) => setPlaces(e.target.checked)} />
          <span>
            Show <b>major places</b> — 277 local units, each with its own government site
          </span>
        </label>

        {places && (
          <div className="blindnote">
            <b>277 circles, drawn once you are zoomed in.</b> The layer has a minimum zoom of 5.5, so
            at this whole-country view the toggle changes nothing you can see. Zoom into a district and
            each local unit appears, sized by how many slopes are documented in it.
          </div>
        )}

        {trails && (
          <div className="blindnote">
            <b>OpenStreetMap, bundled.</b> Every mapped footpath, track and stairway in the
            six regions of Nepal — 23,726 ways, 153,480 points, 5.4 MB. Coloured by recorded
            difficulty: <b style={{ color: "#34d399" }}>easy</b>,{" "}
            <b style={{ color: "#fbbf24" }}>moderate</b>,{" "}
            <b style={{ color: "#f97316" }}>hard</b>, and neutral where OSM records none.
            It is a vector layer, so it stays sharp at any zoom and needs no network — the same
            bundle the offline trip planner reads.
            <div style={{ marginTop: 8, opacity: 0.75 }}>
              Trail data © OpenStreetMap contributors, ODbL 1.0. Nepal&apos;s footpath coverage is
              incomplete: a trail missing here is one nobody has drawn yet.
            </div>
          </div>
        )}

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
        <Link href="/field/" className="phone fieldapp">🚨 Field app — SOS, the board, and the Bluetooth search</Link>
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
            cue: "The day Nepal recorded 167 landslides. 31 of 613 slopes crossed the 24-hour threshold; the season peaked the day before at 149. Say clearly: this is not a forecast — we tested it, and the slopes that failed were not the most loaded.",
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
