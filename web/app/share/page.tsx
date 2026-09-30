"use client";

import Link from "next/link";

/**
 * The awareness surface.
 *
 * A map changes nothing if nobody opens it. This page exists so the finding can leave the
 * screen: a ten-second film of the 2024 monsoon, the still of the peak day, and the one
 * sentence that matters. Everything on it is generated from real data - no illustration.
 */
export default function Share() {
  return (
    <div className="sharewrap">
      <header className="sharehead">
        <h1>Pahiro <span>पहिरो</span></h1>
        <p>
          In the 2024 monsoon, <b>305 of 613 documented landslide-prone slopes in Nepal</b> were
          above the rainfall threshold on a single day — 28 September. On that day Nepal
          recorded <b>167 landslides</b>. And only <b>27.8%</b> of the satellite imagery that
          month had clear ground, so most of those slopes could not be looked at at all.
          <br /><br />
          <b>We then tested whether that ranking finds the slopes that fail. It does not.</b> The
          slopes that actually failed that day ranked at the 55th percentile of the rainfall
          ranking — a coin toss. So this is not a forecast, and the map does not claim to be
          one. It is the list of slopes under load, and the office on the hook for each.
        </p>
      </header>

      <section className="sharemedia">
        <video src="/media/pahiro-monsoon-2024.mp4" controls autoPlay muted loop playsInline />
        <div className="sharelinks">
          <a href="/media/pahiro-monsoon-2024.mp4" download>↓ download the video (mp4)</a>
          <a href="/media/pahiro-monsoon-2024.gif" download>↓ download the gif</a>
          <Link href="/?mode=replay&on=2024-09-28">→ open the live map at that day</Link>
          <Link href="/ar/">→ point a phone at a hillside</Link>
        </div>
      </section>

      <section className="sharefoot">
        <p>
          <b>Nepal can already detect. Nepal cannot dispatch.</b> Pahiro Watch pairs every
          documented slope with the office legally responsible for it — the municipality, the
          division road office, the ward — under the section of law that gives them the duty.
        </p>
        <p className="dim">
          Rainfall: CHIRPS 0.05° daily. Imagery: Sentinel-2 cloudless (EOX/ESA) and Esri World
          Imagery. Threshold: the published Panchpokhari Thangpal curve (118.8 mm/24 h), a local
          fit used as a national reference. This is not detection: it is the list of slopes under
          load, and who is on the hook for each.
        </p>
      </section>
    </div>
  );
}
