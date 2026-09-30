"use client";

import { useEffect, useState } from "react";

/** Registers the service worker and offers install, so the site behaves as an app. */
export default function PWA() {
  const [offline, setOffline] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").then(() => setReady(true)).catch(() => {});
    }
    const on = () => setOffline(!navigator.onLine);
    on();
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
    };
  }, []);

  if (!ready && !offline) return null;
  return (
    <div className="pwa" title={offline ? "Running from cache — no network" : "Saved for offline use"}>
      <i style={{ background: offline ? "#f59e0b" : "#22c55e" }} />
      {offline ? "offline — working from cache" : "saved for offline"}
    </div>
  );
}
