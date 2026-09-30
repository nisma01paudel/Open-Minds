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

## The planner, linked and rendered

`?plan=<sentence>` asks the question on load, the way `?adv=<site-id>` already opens an advisory. The
planner was the one feature that could not be shown or checked from a URL - which is also why its
output had never been looked at, and why the `.plansrc` fix could only be asserted rather than seen.

    ?api=http://127.0.0.1:8085&plan=easy half day walk, a view

    Plan a walk
    Ask in your own words - the open-weight model reads it, the engine decides.
    understood as easy; wants view
    keyword reader (no model server). Start the model server for a better reading;
    the plan is the same engine either way.

The second line is on its OWN line, which it was not before: the two used to concatenate to
"easy; wants viewkeyword reader (no model server)". **The round-57 fix is verified by rendering, not
by reading the stylesheet.**

Then three options, each carrying what the map cannot say:

    (unnamed path)   5.6 km . +0 m . 1h08 . not recorded
    Raichowk - about Rs 24, then 0.8 km on foot
    difficulty not recorded . 68 min . cannot check this from the map data . bus Rs 24

    (unnamed path)   4.1 km . +0 m . 0h49 . not recorded
    Toudol Micro Station - about Rs 24, then 3.4 km on foot

    (unnamed path)   4.0 km . +0 m . 0h48 . not recorded
    Makalbari Bus Station - about Rs 33, trailhead at the stop

    Trail data is OpenStreetMap and Nepali footpath coverage is incomplete. Climb comes from a
    1.2 km terrain grid and is indicative. Bus fares are a dated estimate; routes and schedules
    are not known here.

Three paths near Kathmandu are unnamed in OSM, and the app prints "(unnamed path)" rather than
inventing one. The difficulty field says "not recorded" and "cannot check this from the map data"
rather than guessing a grade from a length. The caveat paragraph names all three limits.

## The false finding immediately before it

The first capture used `--disable-gpu`, which killed WebGL, and the map rendered as an empty white
panel. That looks exactly like a broken map layer. It was my capture, not the app - the same mistake
as grepping the bundle for the phone's labels one round earlier. **A headless browser without
`--use-angle=swiftshader` cannot render this app, and its blank map is a property of the harness.**
