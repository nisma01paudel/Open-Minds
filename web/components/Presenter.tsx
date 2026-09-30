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
  // ?beat=N opens the pitch on a given POSITION, not on the number in the title. There are nine
  // beats labelled 1, 2, 3, 4, 5, 5b, 6, 7, 8 - "5b" is an inserted half-beat that consumes no
  // number - so ?beat=6 opens "5b · Where we are blind". Written down because the divergence looks
  // like an off-by-one when you open ?beat=9 and read a card headed "8". It is not: the titles are
  // labels and the parameter is a position, and both were checked against the array before this
  // comment was written.
  // ?beat=N opens the pitch on a given beat. Two reasons, and the second is the one that mattered:
  // a beat can be linked during a talk, and every beat becomes renderable from a URL - which is how
  // eight of the nine were checked, having never been seen because advancing needs a key press.
  const startBeat = () => {
    if (typeof window === "undefined") return 0;
    const raw = new URLSearchParams(window.location.search).get("beat");
    const n = raw ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(beats.length - 1, Math.trunc(n) - 1));
  };
  const [i, setI] = useState(startBeat);

  useEffect(() => {
    const q = new URLSearchParams(location.search);
    // Both parameters open the pitch; ?beat also asks for its beat's map state, which otherwise only
    // an arrow key would set.
    if (q.get("present") === "1" || q.get("beat")) {
      setOn(true);
      beats[startBeat()].action();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
