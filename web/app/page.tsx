"use client";

import { useEffect, useMemo, useState } from "react";
import SlopeMap, { Frame } from "../components/SlopeMap";

type Feature = {
  properties: {
    id: string; title: string; state: string; r24: number; r72: number;
    authority?: string; legal_basis?: string; source: string;
  };
};

export default function Page() {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [active, setActive] = useState(0);
  const [rows, setRows] = useState<Feature[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch("/data/frames.json")
      .then((r) => r.json())
      .then((f: Frame[]) => {
        setFrames(f);
        // ?f=1 opens straight to a frame, so a specific day can be linked or put on screen.
        const want = Number(new URLSearchParams(location.search).get("f") ?? "0");
        if (Number.isFinite(want) && want >= 0 && want < f.length) setActive(want);
      })
      .catch(() => setErr("could not load frames.json"));
  }, []);

  const frame = frames[active];

  useEffect(() => {
    if (!frame) return;
    fetch(`/data/${frame.file}`)
      .then((r) => r.json())
      .then((g) => setRows(g.features ?? []))
      .catch(() => setRows([]));
  }, [frame]);

  const counts = frame?.counts ?? {};
  const total = (counts.exceeded ?? 0) + (counts.approaching ?? 0) + (counts.below ?? 0);
  const pctAbove = total ? Math.round((100 * (counts.exceeded ?? 0)) / total) : 0;

  const loaded = useMemo(
    () =>
      rows
        .filter((r) => r.properties.state !== "below")
        .sort((a, b) => b.properties.r24 - a.properties.r24)
        .slice(0, 14),
    [rows],
  );

  return (
    <div className="stage">
      <SlopeMap frames={frames.length ? frames : []} activeIndex={active} />

      <header>
        <div className="brand">
          <h1>
            Pahiro Watch <span>पहिरो</span>
          </h1>
          <p>
            Every documented landslide-prone slope in Nepal, from open rainfall data — and the
            office legally responsible for each.
          </p>
        </div>
      </header>

      <aside className="panel">
        <div className="frames">
          {frames.map((f, i) => (
            <button key={f.id} aria-pressed={i === active} onClick={() => setActive(i)}>
              {f.label}
              {f.counts.exceeded ? ` · ${f.counts.exceeded}` : ""}
            </button>
          ))}
          {!frames.length && <span style={{ color: "#64748b", fontSize: 13 }}>{err || "loading…"}</span>}
        </div>

        {frame && (
          <>
            <div className="statgrid">
              <div className="stat">
                <b style={{ color: "var(--exceeded)" }}>{counts.exceeded ?? 0}</b>
                <span>above threshold</span>
              </div>
              <div className="stat">
                <b style={{ color: "var(--approaching)" }}>{counts.approaching ?? 0}</b>
                <span>approaching</span>
              </div>
              <div className="stat">
                <b>{total}</b>
                <span>slopes evaluated</span>
              </div>
              <div className="stat">
                <b>{Math.round(frame.worst_r24)}<small style={{ fontSize: 14 }}> mm</small></b>
                <span>worst 24 h</span>
              </div>
            </div>

            <div className="legend">
              <div><i className="swatch" style={{ background: "var(--exceeded)" }} /> Above the threshold — inspect</div>
              <div><i className="swatch" style={{ background: "var(--approaching)" }} /> Approaching the threshold</div>
              <div><i className="swatch" style={{ background: "var(--below)" }} /> Below the threshold</div>
            </div>

            <h2>Most loaded · {frame.date}</h2>
            <div className="list">
              {loaded.length ? (
                loaded.map((r) => (
                  <div className="row" key={r.properties.id} title={r.properties.authority ?? ""}>
                    <i
                      className="swatch"
                      style={{
                        background:
                          r.properties.state === "exceeded" ? "var(--exceeded)" : "var(--approaching)",
                      }}
                    />
                    <span className="t">{r.properties.title || "Documented slope"}</span>
                    <span className="v">{Math.round(r.properties.r24)}</span>
                  </div>
                ))
              ) : (
                <span style={{ color: "#64748b", fontSize: 13 }}>
                  No slope is above the threshold on this date.
                </span>
              )}
            </div>

            <div className="foot">
              <b>{pctAbove}% of documented slopes</b> are above the rainfall threshold on this
              date. Rainfall:{" "}
              {frame.source === "open-meteo" ? "Open-Meteo (near-real-time)" : "CHIRPS"}. Threshold:
              the published Panchpokhari Thangpal curve, 118.8 mm/24 h — a <b>local</b> fit used as a
              national reference. At 5 km resolution a smaller convective cell is invisible, so this
              under-counts.
              <br />
              <br />
              This is not detection. It is the list of slopes loaded right now, and who is on the
              hook for each.
            </div>
          </>
        )}
      </aside>

      <div className="hint">Drag to rotate · scroll to zoom · click a slope for the responsible office</div>
    </div>
  );
}
