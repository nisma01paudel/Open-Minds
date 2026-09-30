"use client";

/**
 * The operations panel: every handset that has called for help, ranked for search order.
 *
 * This is the screen a district coordinator would actually keep open. It reads one endpoint -
 * /api/v1/triage - because the ranking and the rows it ranks must not be able to disagree: a
 * rank rendered against a row fetched separately is a dashboard that lies during a refresh.
 *
 * The ranking is deterministic and every point traces to a named factor, which is the point. A
 * coordinator can ask "why is this one first" and get an answer they can disagree with, then
 * argue about the weights instead of the output. A model's ranking cannot be audited in the
 * minute available, and would be the only part of this system nobody could check.
 *
 * The caveat travels with the ranking on screen, not only in a docstring: this orders *search*,
 * it cannot see the person, and a low rank is not a reason to ignore a report.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

type Reason = { factor: string; points: number; detail: string };

type Entry = {
  device_id: string;
  score: number;
  band: string;
  people: number | null;
  reasons: Reason[];
  warnings: string[];
  report?: {
    name?: string;
    message?: string;
    created_at?: string;
    lat?: number | null;
    lon?: number | null;
    battery?: number | null;
    reports?: number;
    hops?: number;
    located?: { search_radius_m?: number; centre?: { lat: number; lon: number } } | null;
  } | null;
};

type Board = {
  count: number;
  bands: Record<string, number>;
  ranked: Entry[];
  stats?: Record<string, number>;
  not_a_promise?: string;
};

const BAND_COLOUR: Record<string, string> = {
  critical: "#ff2d20",
  urgent: "#ff9f0a",
  routine: "#7c8ba1",
};

function apiBase(): string {
  if (typeof window === "undefined") return "";
  const q = new URLSearchParams(window.location.search).get("api");
  return (q || "http://127.0.0.1:8080").replace(/\/+$/, "");
}

function ago(iso?: string): string {
  if (!iso) return "unknown";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "unknown";
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export default function AdminPage() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState<string>("");
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${apiBase()}/api/v1/triage`, { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setBoard(await r.json());
      setError("");
      setUpdated(new Date().toLocaleTimeString());
    } catch (e: any) {
      setError(
        `${e.message} — is the field API running? python -m pahiro.api --port 8080`,
      );
    }
  }, []);

  useEffect(() => {
    load();
    // Ten seconds: fast enough that a handset appearing is noticed while you are looking at the
    // screen, slow enough not to hammer a laptop running on a battery in a tent.
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const ranked = board?.ranked ?? [];
  const visible = useMemo(() => (showAll ? ranked : ranked.slice(0, 12)), [ranked, showAll]);

  return (
    <div className="adminwrap">
      <header className="adminhead">
        <div>
          <h1>
            Pahiro <span>operations</span>
          </h1>
          <p>
            Every handset that has called for help, ranked for search order. Deterministic and
            explainable — every point below names the factor that produced it.
          </p>
        </div>
        <div className="adminmeta">
          <div>
            <b>{board?.count ?? "—"}</b> <span>calling</span>
          </div>
          <div>
            <b style={{ color: BAND_COLOUR.critical }}>{board?.bands?.critical ?? "—"}</b>{" "}
            <span>critical</span>
          </div>
          <div>
            <b style={{ color: BAND_COLOUR.urgent }}>{board?.bands?.urgent ?? "—"}</b>{" "}
            <span>urgent</span>
          </div>
          <div>
            <b>{board?.stats?.messages ?? "—"}</b> <span>mesh frames</span>
          </div>
          <button className="adminrefresh" onClick={load}>
            refresh
          </button>
          {updated && <span className="dim">updated {updated}</span>}
        </div>
      </header>

      {error && <div className="adminerr">{error}</div>}

      {board?.not_a_promise && <div className="admincaveat">{board.not_a_promise}</div>}

      {!board && !error && <div className="dim" style={{ padding: 24 }}>Loading…</div>}

      {board && board.count === 0 && (
        <div className="adminempty">
          No handset has called for help. That is the good outcome — this screen is designed to
          be boring.
        </div>
      )}

      <div className="adminlist">
        {visible.map((e, i) => {
          const radius = e.report?.located?.search_radius_m;
          return (
            <article key={e.device_id} className="adminrow">
              <div className="adminrank">
                <span className="adminnum">{i + 1}</span>
                <span className="adminband" style={{ background: BAND_COLOUR[e.band] ?? "#475569" }}>
                  {e.band}
                </span>
              </div>

              <div className="adminbody">
                <div className="adminid">
                  <b>{e.report?.name || e.device_id}</b>
                  <span className="dim">
                    {" "}
                    · {e.people ?? "?"} people · heard {ago(e.report?.created_at)}
                    {e.report?.reports && e.report.reports > 1
                      ? ` · ${e.report.reports} frames (one person)`
                      : ""}
                  </span>
                </div>

                {e.report?.message && <p className="adminmsg">{e.report.message}</p>}

                <div className="adminfacts">
                  <span>
                    {e.report?.lat != null
                      ? `fix ${e.report.lat.toFixed(5)}, ${e.report.lon?.toFixed(5)}`
                      : "no position fix"}
                  </span>
                  {radius != null && <span>search circle {Math.round(radius)} m</span>}
                  {e.report?.battery != null && <span>battery {e.report.battery}%</span>}
                  {e.report?.hops != null && <span>{e.report.hops} hop(s)</span>}
                </div>

                {/* The arithmetic, shown. A score whose parts are hidden cannot be argued with. */}
                <table className="adminwhy">
                  <tbody>
                    {e.reasons.map((r) => (
                      <tr key={r.factor}>
                        <td>{r.factor}</td>
                        <td className="adminpts">+{r.points.toFixed(1)}</td>
                        <td className="dim">{r.detail}</td>
                      </tr>
                    ))}
                    <tr className="adminsum">
                      <td>total</td>
                      <td className="adminpts">{e.score.toFixed(1)}</td>
                      <td className="dim">of 100</td>
                    </tr>
                  </tbody>
                </table>

                {e.warnings.length > 0 && (
                  <ul className="adminwarn">
                    {e.warnings.map((w, k) => (
                      <li key={k}>{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            </article>
          );
        })}
      </div>

      {ranked.length > visible.length && (
        <button className="adminmore" onClick={() => setShowAll(true)}>
          show all {ranked.length}
        </button>
      )}

      <footer className="adminfoot">
        <b>This ranks search order from a radio and a timestamp.</b> It is not a judgement about
        who matters, it cannot see the person, and a low rank is not a reason to ignore a report.
        Weights are in <code>src/pahiro/triage.py</code> and are meant to be argued with.
      </footer>
    </div>
  );
}
