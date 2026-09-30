# The web app, rendered

Until this round the web half had been verified only by build exit codes, by the presence of files,
and by grepping the bundle for strings. It had never been **looked at**. Chrome is on this machine, so
it now has been:

    cd web/out && python3 -m http.server 8901
    chromium --headless=new --no-sandbox --hide-scrollbars \
      --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
      --virtual-time-budget=28000 --window-size=1440,1000 \
      --screenshot=out.png http://127.0.0.1:8901/

## What it shows

A 3D satellite terrain of Nepal - the snow-capped Himalaya across the top, the Terai below - with
Jomsom, Pokhara, Butwal, Kathmandu, Namche Bazaar, Birgunj, Janakpur, Dharan, Ilam and Biratnagar
labelled, and the attribution the imagery requires: **Sentinel-2 cloudless (EOX/ESA), Open-Meteo /
CHIRPS, AWS terrain, OpenFreeMap tiles.**

The panel carries 613 slopes mapped, 0 above threshold on 2026-09-30, the four entry buttons (fly over
it in 3D, the ten-second film, the phone view, the field app), the walk planner, the observability and
trail layers, the legend, the rainfall source with its threshold, and the sentence that matters:

> This is not detection. It is the list of slopes loaded on a given day, each carrying the routing
> key's default duty holder for a local road. Per-report routing, which resolves the actual asset, is
> measured separately on 21 expert-labelled scenarios.

The offline indicator reads **saved for offline** in green.

## The defect that only rendering found

    Plan a walkAsk in your own words — the open-weight model reads it, the engine decides.

`<b>Plan a walk</b>` and `<span>Ask in your own words...</span>` sit inside `<div class="planhead">`,
and **no stylesheet defined `.planhead`**. Both elements are inline, JSX collapses the newline between
them, and the two ran together with no space.

The class existed in the JSX and in no CSS file - which is a shape worth checking for generally: 72
class names are used across `app/` and `components/`, and 15 have no rule in `globals.css`.

**Fixed** by giving `.planhead b` and `.planhead span` block display, and the fix is confirmed by
re-rendering rather than by reading the diff.

## The false finding immediately before it

The first capture used `--disable-gpu`, which killed WebGL, and the map rendered as an empty white
panel. That looks exactly like a broken map layer. It was my capture, not the app - the same mistake
as grepping the bundle for the phone's labels one round earlier. **A headless browser without
`--use-angle=swiftshader` cannot render this app, and its blank map is a property of the harness.**
