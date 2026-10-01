"use client";

import { dataUrl } from "../../lib/base";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Site = { id: string; title: string; lat: number; lon: number; authority?: string;
              legal_basis?: string; r: (number | null)[] };
type Timeline = { days: string[]; threshold_mm_24h: number; sites: Site[] };

const APPROACH = 0.8;
const R_EARTH = 6371.0088;

const toRad = (d: number) => (d * Math.PI) / 180;
const toDeg = (r: number) => (r * 180) / Math.PI;

function distanceKm(aLat: number, aLon: number, bLat: number, bLon: number) {
  const dp = toRad(bLat - aLat), dl = toRad(bLon - aLon);
  const h = Math.sin(dp / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dl / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(h)));
}

function bearingDeg(aLat: number, aLon: number, bLat: number, bLon: number) {
  const p1 = toRad(aLat), p2 = toRad(bLat), dl = toRad(bLon - aLon);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

export default function AR() {
  const video = useRef<HTMLVideoElement>(null);
  const [tl, setTl] = useState<Timeline | null>(null);
  const [pos, setPos] = useState<{ lat: number; lon: number } | null>(null);
  const [heading, setHeading] = useState<number | null>(null);
  const [pitch, setPitch] = useState(0);
  const [camErr, setCamErr] = useState("");
  const [camOn, setCamOn] = useState(false);
  const [dayIdx, setDayIdx] = useState(0);
  const [big, setBig] = useState(false);

  useEffect(() => {
    fetch(dataUrl("/data/timeline.json")).then((r) => r.json()).then((t: Timeline) => {
      setTl(t); setDayIdx(t.days.length - 1);
    }).catch(() => {});
  }, []);

  const startCamera = useCallback(async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } }, audio: false,
      });
      if (video.current) { video.current.srcObject = s; await video.current.play(); }
      setCamOn(true); setCamErr("");
    } catch (e: any) {
      setCamErr(e?.message ?? "camera unavailable");
    }
  }, []);

  const startSensors = useCallback(() => {
    navigator.geolocation?.watchPosition(
      (p) => setPos({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => {}, { enableHighAccuracy: true, maximumAge: 5000 },
    );
    const handler = (e: any) => {
      // iOS exposes compass heading; Android gives absolute orientation.
      const h = e.webkitCompassHeading ?? (e.absolute ? e.alpha : null);
      if (h !== null && h !== undefined) setHeading((360 - h + 360) % 360);
      if (e.beta !== null && e.beta !== undefined) setPitch(e.beta - 90);
    };
    const DOE: any = (window as any).DeviceOrientationEvent;
    if (DOE?.requestPermission) {
      DOE.requestPermission().then((r: string) => {
        if (r === "granted") window.addEventListener("deviceorientationabsolute", handler, true),
          window.addEventListener("deviceorientation", handler, true);
      });
    } else {
      window.addEventListener("deviceorientationabsolute", handler, true);
      window.addEventListener("deviceorientation", handler, true);
    }
  }, []);

  // Nearest documented slopes, with live state for the selected day.
  const nearby = useMemo(() => {
    if (!tl || !pos) return [];
    const threshold = tl.threshold_mm_24h;
    return tl.sites
      .map((s) => {
        const d = distanceKm(pos.lat, pos.lon, s.lat, s.lon);
        const v = s.r[dayIdx];
        const state = v === null || v === undefined ? "unknown"
          : v >= threshold ? "exceeded" : v >= threshold * APPROACH ? "approaching" : "below";
        return { ...s, d, bearing: bearingDeg(pos.lat, pos.lon, s.lat, s.lon), v, state };
      })
      .filter((s) => s.d < 25)
      .sort((a, b) => a.d - b.d)
      .slice(0, 24);
  }, [tl, pos, dayIdx]);

  const COLOUR: Record<string, string> = {
    exceeded: "#ff2d20", approaching: "#ff9f0a", below: "#94a3b8", unknown: "#475569",
  };

  const visible = nearby.filter((s) => {
    if (heading === null) return true;
    const rel = ((s.bearing - heading + 540) % 360) - 180;
    return Math.abs(rel) < 55;
  });

  return (
    <div className="arstage">
      <video ref={video} playsInline muted className="arcam" />
      {!camOn && (
        <div className="arstart">
          <h1>Pahiro <span>AR</span></h1>
          <p>
            Point your phone at the hillside. Every documented slope in view shows its rainfall
            state for the selected day — and the office legally responsible for it.
          </p>
          <button onClick={() => { startCamera(); startSensors(); }}>
            Enable camera &amp; location
          </button>
          {camErr && <p className="err">{camErr}</p>}
          <p className="tiny">No video leaves the device. No account, no key, no upload.</p>
        </div>
      )}

      {camOn && (
        <>
          <div className="arhud">
            <b>{tl?.days[dayIdx] ?? "—"}</b>
            <span>{pos ? `${pos.lat.toFixed(3)}, ${pos.lon.toFixed(3)}` : "locating…"}</span>
            <span>{heading === null ? "no compass" : `facing ${Math.round(heading)}°`}</span>
            <button onClick={() => setBig((b) => !b)}>{big ? "fewer" : "more"}</button>
          </div>

          <div className="aroverlay">
            {visible.slice(0, big ? 14 : 6).map((s) => {
              const rel = heading === null ? 0 : ((s.bearing - heading + 540) % 360) - 180;
              const x = 50 + (rel / 55) * 46;
              const y = 46 - Math.max(-26, Math.min(26, pitch)) * 0.7;
              return (
                <div key={s.id} className="marker" style={{ left: `${x}%`, top: `${y + (s.d % 7) * 3}%` }}>
                  <div className="pin" style={{ background: COLOUR[s.state] }} />
                  <div className="card">
                    <b>{s.v === null || s.v === undefined ? "—" : Math.round(s.v)} mm</b>
                    <div className="t">{s.title || "Documented slope"}</div>
                    <div className="d">{s.d.toFixed(1)} km · {Math.round(s.bearing)}°</div>
                    <div className="a">{s.authority ?? "no cited authority"}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="arfoot">
            <input type="range" min={0} max={(tl?.days.length ?? 1) - 1} value={dayIdx}
                   onChange={(e) => setDayIdx(Number(e.target.value))} />
            <div className="arlegend">
              <span><i style={{ background: COLOUR.exceeded }} /> above</span>
              <span><i style={{ background: COLOUR.approaching }} /> approaching</span>
              <span><i style={{ background: COLOUR.below }} /> below</span>
              <span className="sp" />
              <Link href="/">full map →</Link>
            </div>
            {!pos && <div className="tiny">Allow location to place slopes in the real world.</div>}
          </div>
        </>
      )}
    </div>
  );
}
