"use client";

/**
 * One place, everything we know about it, offline.
 *
 * This is the screen the whole objective was pointing at. Pick a spot and it answers: which region
 * you are in, what each month is like, what the valley looks like, which trails leave from here, who
 * is legally responsible for the ground, and where the nearest bus is - from one API call, against
 * files that are already on the device.
 *
 * It also prints what it COULD NOT answer. A lookup that hides its gaps reads as complete when it is
 * not, and "no trails here" and "we have not mapped here" are different sentences.
 */

import { useCallback, useEffect, useState } from "react";

type Month = { month: number; name: string; rain_mm_per_day: number; dry_day_pct: number;
               t_max_c: number | null; t_min_c: number | null; validated: boolean };
type Place = {
  lat: number; lon: number;
  region?: { key: string; name: string; distance_km: number };
  seasons?: Month[];
  panorama?: string;
  trails?: { name: string | null; distance_m: number; sac: string | null }[];
  duty?: { slope: string; distance_m: number; office: string; legal_basis: string;
           local_unit?: string | null; district?: string | null; website?: string | null };
  susceptibility?: number;
  bus?: { stop: string | null; distance_m: number; region: string };
  unresolved?: string[];
  sources?: Record<string, string>;
};

const SPOTS = [
  { name: "Kathmandu", lat: 27.7047, lon: 85.3146 },
  { name: "Pokhara", lat: 28.2096, lon: 83.9856 },
  { name: "Namche", lat: 27.8069, lon: 86.7140 },
  { name: "Beni", lat: 28.35, lon: 83.57 },
  { name: "Jomsom", lat: 28.7806, lon: 83.7228 },
  { name: "Langtang", lat: 28.2116, lon: 85.5604 },
];

export default function PlacePage() {
  const [spot, setSpot] = useState(SPOTS[0]);
  const [d, setD] = useState<Place | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const look = useCallback(async (s: { name: string; lat: number; lon: number }) => {
    setBusy(true); setErr(null); setD(null);
    try {
      const r = await fetch(`/api/v1/place?lat=${s.lat}&lon=${s.lon}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setD(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void look(spot); }, [spot, look]);

  const best = (d?.seasons ?? []).reduce<Month | null>(
    (a, m) => (!a || m.rain_mm_per_day < a.rain_mm_per_day ? m : a), null);
  const wettest = (d?.seasons ?? []).reduce<Month | null>(
    (a, m) => (!a || m.rain_mm_per_day > a.rain_mm_per_day ? m : a), null);

  return (
    <main style={{ padding: "1.2rem", maxWidth: 1000, margin: "0 auto", lineHeight: 1.5 }}>
      <h1 style={{ marginBottom: ".2rem" }}>One place, everything we know</h1>
      <p style={{ opacity: .8, marginTop: 0 }}>
        Every field below comes from a file this app already carries. It works with the radio off,
        and it tells you what it could not answer as well as what it could.
      </p>

      <div style={{ display: "flex", gap: ".4rem", flexWrap: "wrap", margin: ".9rem 0 1.2rem" }}>
        {SPOTS.map((s) => (
          <button key={s.name} onClick={() => setSpot(s)}
                  style={{ padding: ".35rem .8rem", cursor: "pointer",
                           fontWeight: s.name === spot.name ? 700 : 400,
                           opacity: s.name === spot.name ? 1 : .65 }}>{s.name}</button>
        ))}
      </div>

      {busy && <p>Looking up {spot.name}&hellip;</p>}
      {err && <p style={{ color: "#c66" }}>The lookup failed: {err}. Start the API to use this page.</p>}

      {d && (
        <div style={{ display: "grid", gap: "1.4rem" }}>
          <section>
            <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Where you are</h2>
            {d.region
              ? <p style={{ margin: 0 }}>
                  Inside the <b>{d.region.name}</b> data, {d.region.distance_km} km from its centre.{" "}
                  {d.panorama && <a href="/panorama">Look around this valley &rarr;</a>}
                </p>
              : <p style={{ margin: 0, opacity: .75 }}>Outside every region this app has mapped.</p>}
          </section>

          {d.seasons && (
            <section>
              <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>When to go</h2>
              <p style={{ margin: "0 0 .6rem", opacity: .8 }}>
                No month is labelled good or bad. A farmer, a trekker and a paraglider want different
                weather from the same month, so here are the numbers and the decision is yours.
                {best && wettest && <> Driest is <b>{best.name}</b> at {best.rain_mm_per_day} mm a day;
                  wettest is <b>{wettest.name}</b> at {wettest.rain_mm_per_day}.</>}
              </p>
              <div style={{ display: "flex", gap: 3, alignItems: "flex-end", height: 90 }}>
                {d.seasons.map((m) => (
                  <div key={m.month} title={`${m.name}: ${m.rain_mm_per_day} mm/day, ${m.dry_day_pct}% dry days`}
                       style={{ flex: 1, textAlign: "center" }}>
                    <div style={{ height: Math.max(2, m.rain_mm_per_day * 3.2),
                                  background: m.validated ? "#4a7" : "#556",
                                  borderRadius: "3px 3px 0 0" }} />
                    <div style={{ fontSize: ".65rem", opacity: .7 }}>{m.name.slice(0, 1)}</div>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: ".8rem", opacity: .7, marginTop: ".4rem" }}>
                Green bars are months cross-checked against this project&rsquo;s own CHIRPS
                measurement; grey ones are model output only.
              </p>
            </section>
          )}

          <section>
            <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Walking from here</h2>
            {d.trails && d.trails.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                {d.trails.map((t, i) => (
                  <li key={i}>
                    {t.name ?? <i>an unnamed path</i>} &mdash; {(t.distance_m / 1000).toFixed(2)} km
                    {t.sac ? `, graded ${t.sac}` : ""}
                  </li>
                ))}
              </ul>
            ) : <p style={{ margin: 0, opacity: .75 }}>No mapped trail within 5 km (see below).</p>}
          </section>

          {d.duty && (
            <section>
              <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Who is responsible for the ground</h2>
              <p style={{ margin: 0 }}>
                Nearest documented slope: <b>{d.duty.slope}</b>, {d.duty.distance_m} m away.
                {d.duty.local_unit && <> It sits in <b>{d.duty.local_unit}</b>
                  {d.duty.district ? `, ${d.duty.district} district` : ""}. </>}
                {d.duty.website && <a href={d.duty.website}>The office&rsquo;s own site &rarr;</a>}
              </p>
              <p style={{ margin: ".3rem 0 0", fontSize: ".85rem", opacity: .8 }}>
                Duty holder: {d.duty.office}. Cited to {d.duty.legal_basis}.
              </p>
            </section>
          )}

          <section style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
            {d.susceptibility !== undefined && (
              <div>
                <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Published susceptibility</h2>
                <p style={{ margin: 0 }}>
                  <b>{d.susceptibility.toFixed(3)}</b> at the nearest sampled slope &mdash;
                  Kincey et al. 2023, national 30 m, CC-BY-4.0.
                </p>
              </div>
            )}
            {d.bus && (
              <div>
                <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Bus</h2>
                <p style={{ margin: 0 }}>
                  {d.bus.stop ?? <i>an unnamed stop</i>} &mdash; {d.bus.distance_m} m away.
                </p>
              </div>
            )}
          </section>

          {d.unresolved && d.unresolved.length > 0 && (
            <section style={{ borderLeft: "3px solid #a74", paddingLeft: ".9rem" }}>
              <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>What this could not answer</h2>
              <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                {d.unresolved.map((u, i) => <li key={i}>{u}</li>)}
              </ul>
            </section>
          )}

          {d.sources && (
            <section>
              <h2 style={{ fontSize: "1.05rem", margin: "0 0 .3rem" }}>Where each number came from</h2>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: ".9rem", opacity: .85 }}>
                {Object.entries(d.sources).map(([k, v]) => <li key={k}><b>{k}</b>: {v}</li>)}
              </ul>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
