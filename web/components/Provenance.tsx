"use client";
import { dataUrl } from "../lib/base";
import { useEffect, useState } from "react";

type Item = { id: string; label: string; value: string | number;
              file: string; how: string; caveat: string };
type Doc = { note: string; items: Item[] };

/**
 * Where the numbers come from.
 *
 * This project's whole argument is that a figure should never appear without what it does not mean,
 * and until now that discipline lived in the tests and in prose. A reader on the map saw "613" and
 * "534" and had to take them on trust, or go and find the guard that checks them.
 *
 * So every headline number on this screen can now explain itself: the file it is derived from, how it
 * was measured, and the thing it does not say. The caveats are the same sentences the guards enforce,
 * which is the point - this is the machinery, shown rather than described.
 */
export default function Provenance() {
  // ?prov=1 opens it on load, like ?blind=1 and ?places=1. Two reasons and the second is the one
  // that mattered: a judge can be sent straight to it, and it can be photographed without a mouse -
  // the panel whose entire subject is "check the number" was otherwise unverifiable.
  const [doc, setDoc] = useState<Doc | null>(null);
  const [open, setOpen] = useState(
    () => typeof window !== "undefined" &&
          new URLSearchParams(window.location.search).get("prov") === "1");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open || doc) return;
    fetch(dataUrl("/data/provenance.json"))
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setDoc)
      .catch(() => setErr("the provenance file could not be loaded"));
  }, [open, doc]);

  return (
    <>
      <button className="provbtn" onClick={() => setOpen((v) => !v)}>
        {open ? "× close" : "where do these numbers come from?"}
      </button>
      {open && (
        <div className="provpanel">
          {err && <p className="proverr">{err}</p>}
          {doc && (
            <>
              <p className="provnote">{doc.note}</p>
              {doc.items.map((i) => (
                <div className="provitem" key={i.id}>
                  <div className="provhead">
                    <span className="provval">{i.value}</span>
                    <span className="provlab">{i.label}</span>
                  </div>
                  <div className="provfile">{i.file}</div>
                  <p className="provhow">{i.how}</p>
                  <p className="provcav"><b>What it does not say:</b> {i.caveat}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </>
  );
}
