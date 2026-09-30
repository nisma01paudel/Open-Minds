"use client";

import { useEffect, useState } from "react";

/** Registers the service worker and offers install, so the site behaves as an app. */
export default function PWA() {
  const [offline, setOffline] = useState(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      // THE FAILURE HAS TO BE VISIBLE. This was `.catch(() => {})`, so a service worker that failed
      // to register left `ready` false, the component returned null, and there was NO INDICATOR AT
      // ALL - the app simply was not offline and said nothing. The whole product rests on working
      // with the radio off, and a user who cannot tell "saved" from "not saved" only finds out when
      // they need it, which is the worst possible moment.
      navigator.serviceWorker
        .register("/sw.js")
        .then(() => setReady(true))
        .catch((e) => {
          console.warn("[pahiro] service worker failed to register:", e);
          setFailed(true);
        });
    } else {
      setFailed(true); // no service worker at all means no offline, and that is worth saying
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

  if (!ready && !offline && !failed) return null;
  if (failed && !offline) {
    return (
      <div className="pwa"
           title="The service worker did not register, so this page is NOT saved for offline use. Reload to retry.">
        <i style={{ background: "#ef4444" }} />
        not saved for offline
      </div>
    );
  }
  return (
    <div className="pwa" title={offline ? "Running from cache — no network" : "Saved for offline use"}>
      <i style={{ background: offline ? "#f59e0b" : "#22c55e" }} />
      {offline ? "offline — working from cache" : "saved for offline"}
    </div>
  );
}
