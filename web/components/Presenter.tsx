"use client";

import { useEffect, useState } from "react";

export type Beat = {
  title: string;
  cue: string;                 // what to say, or paraphrase
  action: () => void;
  href?: string;               // a beat that lives on another page
};

/**
 * Presenter mode: the five-minute demo, driven from the keyboard.
 *
 * The failure this prevents is not technical. It is standing in front of a room, five
 * minutes on the clock, fumbling between a map, a 3D view and a phone. So the beats are
 * pre-set, the arrow keys move through them, and the cue is on screen where only the
 * presenter can read it.
 *
 *   ?present=1     then  ->  to advance,  <-  to go back,  Esc to leave
 */
export default function Presenter({ beats }: { beats: Beat[] }) {
  const [on, setOn] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    if (new URLSearchParams(location.search).get("present") === "1") setOn(true);
  }, []);

  useEffect(() => {
    if (!on) return;
    const go = (n: number) => {
      const k = Math.max(0, Math.min(beats.length - 1, n));
      setI(k);
      beats[k].action();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") { e.preventDefault(); go(i + 1); }
      else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(i - 1); }
      else if (e.key === "Enter" && beats[i].href) { window.location.href = beats[i].href!; }
      else if (e.key === "Escape") setOn(false);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [on, i, beats]);

  if (!on) {
    return (
      <button className="presenter-off" onClick={() => { setOn(true); beats[0].action(); }}
              title="Guided demo: arrow keys advance">
        ▶ Presenter mode
      </button>
    );
  }

  const b = beats[i];
  return (
    <div className="presenter">
      <div className="pbar">
        {beats.map((x, k) => (
          <button key={k} className={k === i ? "on" : ""} onClick={() => { setI(k); x.action(); }}>
            {k + 1}
          </button>
        ))}
        <span className="pcount">{i + 1} / {beats.length}</span>
        <button className="px" onClick={() => setOn(false)} title="Esc">✕</button>
      </div>
      <div className="pcue">
        <b>{b.title}</b>
        <span>{b.cue}</span>
        <div className="pkeys">
          <kbd>←</kbd><kbd>→</kbd> move
          {b.href && <><kbd>Enter</kbd> open {b.href}</>}
          <kbd>Esc</kbd> exit
        </div>
      </div>
    </div>
  );
}
