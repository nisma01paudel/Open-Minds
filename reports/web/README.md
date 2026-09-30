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

## /field/ - the last surface in the product, now seen

The SOS button in the header links here, and this page had never been rendered. It is the emergency
interface rather than a map:

    Pahiro Field पहिरो                                      online
    SEND A DISTRESS REPORT
    Location: unavailable (User denied Geolocation).
              The report will still be sent - describe where you are.
    [ What is happening: "House buried by the slide, two of us inside" ]
    People with me [1]        Battery % [auto]        Name [optional]
    [                        SEND SOS                        ]
    Works with no signal. If the network is down the report is kept on this phone and sent the
    moment a connection appears - or carried by someone else's phone over Bluetooth.
    WAITING TO SEND
    Nothing queued.
    SOS  .  Board  .  Chat  .  Search  .  भाग्नुहोस्  .  More

**The geolocation line is the one worth looking at.** A headless browser denies geolocation, so this
frame is a real denial - and the page does not block, does not show a spinner and does not pretend to
know where it is. It says the location is unavailable, says **why**, and tells the person the report
will still be sent with a description instead.

Every other failure in this project follows the same rule, and here it applies to someone who is
having the worst hour of their life.

`Battery %` defaults to `auto` - reading the device rather than asking a person trapped under a slide
what their charge level is. `Nothing queued` states the queue is empty rather than leaving a blank.

Every page and every tab in this product has now been rendered.

## The third responsive hide, checked and left alone

Round 62 swept the stylesheet for `display: none` and found three rules. Two were defects and are
fixed. The third:

    @media (max-width: 760px) { .stage header p { display: none; } }

hides the one-sentence description under the title - "Every documented landslide-prone slope in Nepal,
each carrying the routing key's default duty holder for a local road - and the statute that says so."

Checked rather than assumed. The same explanation appears in the sidebar as its closing note:

    This is not detection. It is the list of slopes loaded on a given day, each carrying the
    routing key's default duty holder for a local road. Per-report routing, which resolves the
    actual asset, is measured separately on 21 expert-labelled scenarios.

and `.panel` is `overflow-y: auto` with a styled scrollbar, so nothing in the sidebar is unreachable
at a narrow width. At 700px the app still says what it is, in more detail than the hidden line.

So this one is a judgement about space that happens to be covered elsewhere, not a silent hide. Left
as it is, and recorded here so the next sweep does not re-open it.

## The whole internet, unavailable, and the map still draws

The offline claim had been verified on the phone (airplane mode, `dumpsys` showing no default
network, identical trail distances) and never on the web. It can be tested directly: Chromium will
blackhole every host except localhost.

    chromium --host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1" ...

**The map rendered anyway** - the same 3D terrain, the same ten labelled cities, the same 613-slope
panel - because the basemap is bundled rather than fetched:

    web/out/data/terrain-texture.jpg

So the web app's national view does not need a connection, and the attribution line under it still
names the sources the bundled data came from (Sentinel-2 cloudless, Open-Meteo/CHIRPS, AWS terrain)
because attribution is owed whether or not the request is live.

### What this did not test

The `#maperr` notice - the one added when a broken style once rendered an empty map that looked like a
styling choice. Blackholing the network did not trigger it, because nothing failed: the app was
correctly offline. The handler is wired (`el.style.display = "block"`, with an `info` class that
distinguishes "out of wifi range" from a real error), and **the live path is still unexercised.** It is
named rather than assumed to work, and reaching it would need a deliberately broken tile source rather
than an absent one.

## The SOS link that was hidden on phones

Sweeping the stylesheet for other responsive hides after the advisory one turned up two more, both at
760px:

    @media (max-width: 760px) { .phone { display: none; } }
    @media (max-width: 760px) { .stage header p { display: none; } }

`.phone` is used by two links. Hiding the first is right:

    "Open the phone view - point it at a hillside"   -> /ar/

You are already on a phone. Hiding the second is not:

    "Field app - SOS, the board, and the Bluetooth search"   -> /field/

/field/ is a web page, the SOS is for the device most likely to need it, and the rule removed the
entry point to the other half of the project on exactly the screen somebody would be holding. At
700px that half of the product was unreachable from the front page.

**Fixed** by distinguishing the two: `.phone:not(.fieldapp)` is still hidden below 760px, and
`.phone.fieldapp` moves into the flow instead. Re-rendered at 700px and the SOS button is there, on
its own row, while "Open the phone view" correctly stays hidden.

`.stage header p` remains hidden below 760px. That is a judgement about space rather than a defect,
and it is recorded here rather than changed.

## Narrow viewports, where two defects were real

Everything above was captured at 1440-1600 px. At **860 px** two things were wrong, and unlike the five
alarms of the previous rounds, both were genuine.

**1. The action buttons overlapped and clipped.** "Fly over it in 3D" cut off, "Share the 10-second
film" running underneath the next button. Four links in a flex row with no wrap:

    .topactions { position: absolute; display: flex; gap: 9px; align-items: center; }

**Fixed** with `flex-wrap: wrap; row-gap: 6px`.

**2. The advisory was silently absent.** `?adv=<site>` on an 860 px window produced no advisory and no
explanation, because:

    @media (max-width: 900px) { .advpanel { display: none; } }

That is the same silent hide as the five panels fixed on the phone - a section that is not there and a
section that cannot be shown look identical. **Fixed** with a note that appears only below 900 px:

> The advisory for this slope is shown on a wider window (over 900 px), or in the field app, which
> carries it offline. Nothing has been hidden except the space to print it.

### And the fix introduced a defect, which re-rendering caught

The note was first placed at `top: 74px`. The action buttons are at `top: 84px`, so **the note covered
them**. Reading the CSS diff would not have shown that; re-rendering did, in one frame. It now sits at
`bottom: 42px`, clear of everything.

### And one edit silently did nothing

Applying that move, the heredoc ran from the wrong directory, so `.venv/bin/python` did not resolve,
the script never ran, and the build rebuilt unchanged CSS and exited 0. **The screenshot's byte size
was identical to the previous capture, which is what gave it away.** Comparing artefacts is what
caught an edit that reported success and changed nothing.

## The three linked pages, none of which had been rendered

Beats 6, 7 and 8 link away from the map, so `/fly/`, `/ar/` and `/share/` are part of the product and
had never been looked at either.

### /fly/ - the 3D flythrough

A 3D-extruded Nepal with real vertical relief, the Himalaya standing as a jagged wall and the 613
documented slopes as glowing markers over it, a timeline slider, pause and manual-camera controls, and
a date readout. Beneath it, the two things such a view is most likely to mislead about:

    Elevation: AWS Terrain Tiles . Imagery: Esri World Imagery . Rainfall: CHIRPS .
    Vertical scale exaggerated 12x - real relief is about 1% of Nepal's width.
    The threshold is a published local fit used as a national reference.

An exaggerated-relief view that did not say so would be the same defect as a map that did not name its
day. It says so.

### /ar/ - the phone view

A permission gate, and it renders the gate rather than a broken view when there is no camera - which
is what a headless browser is.

    Pahiro AR
    Point your phone at the hillside. Every documented slope in view shows its rainfall
    state for the selected day - and the office legally responsible for it.
    [ Enable camera & location ]
    No video leaves the device. No account, no key, no upload.

The last line is the claim that makes a camera permission reasonable, and it is on the button's row.

### /share/ - the link you send someone

Confirms the round-44 correction on screen: **31 of 613 documented landslide-prone slopes were above
the rainfall threshold on a single day - 28 September**, followed by the negative result that gives
the project its shape:

    We then tested whether that ranking finds the slopes that fail. It does not. The slopes that
    actually failed ranked at the 53rd and 55th percentile of the rainfall ranking - a coin toss.

Below it the ten-second film with download links and links onward to the live map at that day and to
the AR view.

## Presenter mode, which is what actually wins the room

`?present=1` had never been rendered either. It is the pitch: nine beats with a numbered bar and a
counter, each beat a card over the map, advanced with arrow keys and left with Esc.

    1 . The national picture
    Every documented landslide-prone slope in Nepal - 613 of them - on real Sentinel-2 imagery,
    each carrying the routing key's default duty holder for a local road, cited to the statute.
    Say "default": per-report routing, which resolves the actual asset, is measured separately on
    21 expert-labelled scenarios.

The honesty caveat is in the FIRST beat, not buried in a limitations slide, and it tells the presenter
what to say out loud ("Say 'default'") rather than leaving them to paraphrase it. That is the same
instinct as the phone's live-versus-cited labels, applied to the person holding the clicker.

### The overlap I nearly reported

The beat bar at the bottom left crosses the sidebar's last line of text. I checked before writing it up
as a defect:

    .presenter { position: absolute; left: 0; right: 0; bottom: 0;
      background: linear-gradient(0deg, rgba(5,7,13,.94), rgba(5,7,13,0)); }

The overlay is deliberately full width with a gradient that fades to transparent at its top edge, so
content behind it shows faintly there. That is the intended effect, not a bug, and whether it reads
well is a judgement rather than a defect.

Third time in four rounds that checking before reporting turned a suspected defect into no defect.
The pattern is now cheap enough to be a habit: every time something looks wrong, read the rule that
produced it.

## The false finding immediately before it

The first capture used `--disable-gpu`, which killed WebGL, and the map rendered as an empty white
panel. That looks exactly like a broken map layer. It was my capture, not the app - the same mistake
as grepping the bundle for the phone's labels one round earlier. **A headless browser without
`--use-angle=swiftshader` cannot render this app, and its blank map is a property of the harness.**
