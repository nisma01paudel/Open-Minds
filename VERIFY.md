# How to verify this submission

A judge has limited time and no reason to trust a README. This file is the short path: what to
run, in order, and **what each check has actually caught** — because a check that has never
failed is a check nobody should believe.

Setup is in [SUBMISSION.md](SUBMISSION.md#run-it). It is not repeated here on purpose: an
instruction written out in several places drifts, and this project has already been bitten by
exactly that — the install line once omitted the `crypto` extra in three files at once, so a
fresh clone silently skipped the whole sealing layer while the suite reported success.

## The five commands, and what they prove

```bash
.venv/bin/python -m pytest -q            # the suite
.venv/bin/python scripts/verify_repo.py  # submission readiness
.venv/bin/python scripts/check_beacon_parity.py   # Python and JS agree on the beacon
.venv/bin/python scripts/check_seal_parity.py     # Python and the browser agree on sealing
.venv/bin/python scripts/mutate_check.py          # the suite can FAIL
```

```bash
cd web && npm ci && npm run build          # the demo the film shows, from a clean checkout
```

The web build is worth running because it is the surface the video shows. It is a static export:
six routes (`/`, `/admin`, `/ar`, `/fly`, `/share`), and `out/` must contain the map data —
`timeline.json`, `terrain.bin`, the slopes geojson and 34 offline tiles. All three of the data
files were **missing from the repository** until round 21, so a clone built an app with a blank
map. Build a clone, not your working tree: a checkout that already has the data cannot show you
this.

```bash
cd mobile && flutter build apk --release     # the app phone-installable, not just tested
```

**This is the strongest single check in the repository**, and it was the last one to be run. Everything
else verifies that the logic is right; this verifies that the product exists as something a person
can install. It writes an APK under mobile/build/app/outputs/flutter-apk/ - **48.5 MB**, built and
confirmed - and it takes about thirty-five minutes cold, because the first Gradle build downloads its
distribution and the Compose dependencies.

Nothing in it is generated into the repository: `mobile/build/` is gitignored, so the artefact is a
command rather than 50 MB of history.

And check what ended up inside it, because a phone app that cannot reach its offline data is a
phone app that needs the network:

```bash
unzip -l mobile/build/app/outputs/flutter-apk/app-release.apk | grep flutter_assets/assets
# assets/terrain.bin        851,968
# assets/terrain.json           303
# assets/trails.geojson   5,684,443     <- the whole six-region bundle
```

Those three files are the offline claim. If they are not in the APK, nothing else on this page
matters.

### The web app's offline shell, against the deployed export

The service worker precaches fifteen URLs. `verify_repo.py` checks them against `web/public/`, but
what a browser actually receives is `web/out/` - and a file present in one need not reach the other.

```bash
python - <<'EOF'
import re, pathlib
sw = pathlib.Path("web/public/sw.js").read_text()
urls = set(re.findall(r'"(/data/[^"]+|/icons/[^"]+|/manifest\.webmanifest)"', sw))
missing = [u for u in sorted(urls) if not (pathlib.Path("web/out") / u.lstrip("/")).exists()]
print(f"{len(urls)} precached, {len(missing)} missing from the export")
EOF
```

Confirmed: **15 of 15 present** in the built export, including the 5.42 MB trail bundle, the terrain
grid and the twelve other files the app reads. Every one of them is a file the browser will have
after a single visit and keep with the radio off.

And then actually serve it, because a file on disk is not a file a browser can fetch:

```bash
cd web/out && python3 -m http.server 8097
# then fetch every URL the service worker names, plus each route
```

Confirmed: **22 of 22 return 200 with a non-empty body** - all fifteen precached URLs, the six app
routes, and `sw.js` itself. The content types are right where they matter: the 5.68 MB trail bundle
is served as `application/geo+json`, `terrain.bin` as `application/octet-stream`, the manifest as
`application/manifest+json`, and the service worker as `text/javascript` - a service worker served
with the wrong type is silently not a service worker, and the app quietly stops working offline
while looking perfectly fine online.

The last one is the one worth your time. **A passing suite is not evidence until you know it can
fail.** `mutate_check.py` breaks six load-bearing constants on purpose — the beacon's frame
size, the weight of a headcount in triage, the battery level at which a phone stops scanning,
the flood margin the escape planner must clear, the hop limit, the AEAD nonce length — and
reports how many the suite noticed. It reverts every mutation with `git checkout`.

## What these checks have caught

Not hypotheticals. Each of these was found by a check in this repository, after the code
already looked finished:

| Found | How |
|---|---|
| A **safety default** (`DEFAULT_RISE_M`, the flood margin) could be halved with the entire suite still green — every test passed `rise_m` explicitly, so nothing pinned the default | `mutate_check.py` |
| **Four of fourteen** film clips were built with a caption and **no voice**, about fifty seconds of the demo | The narration-key check in `tests/test_offline_ai.py` |
| The **submission video spoke a claim the repository retracts** — the Nepali narration asserted per-slope routing the map does not do | Reading the narration against the app |
| The **required deliverable was not in the repository** — the demo film was gitignored | `tests/test_doc_claims.py`, on a fresh clone |
| The **web demo's data was not in the repository** — 3.7 MB of slope geometry, terrain and advisories, so a clone rendered an empty map | The same test, one step further |
| The **"one command" demo needed a 1.1 GB model** at a path outside the repository, and failed with no explanation | Running `scripts/demo.sh` on a clean clone |
| The **install line omitted the `crypto` extra in three files at once** | `test_every_copy_of_the_install_command_asks_for_the_same_extras` |
| A **skip counted as a pass** — the cross-language checks skip without node, and the verifier reported OK | `scripts/verify_repo.py` |

The pattern in every row: the thing was verified where it was built, and broken where it was
used. That is why the commands above are run from a clean clone, and why
`verify_repo.py` treats a **skipped** cross-language check as a failure rather than a pass.

## The safety-critical path, exercised live

The escape planner is the feature a life depends on, so it is worth seeing rather than trusting. With
the API running:

```bash
curl -s "http://127.0.0.1:8080/api/v1/escape?lat=28.35&lon=83.57&rise_m=5"
```

    reachable  true
    target     28.348115, 83.589478  at 1058 m   (you are at 1043 m)
    climb      15 m over 1076 m, bearing 90 east, about 18 minutes
    why        uphill ground that clears the expected 5 m rise by 2 m;
               the local fall line runs 125 degrees
    advice     "... This is terrain-only, from a 1077 m grid, and it cannot see bridges,
               culverts or the water itself. Move away from the stream first, then uphill."

Three things to notice. It gives a **direction, a distance and a height**, not a point on a map. It
says **why** it chose that ground. And the **caveat travels with the advice** rather than sitting in a
document - a person reading that sentence in a flood knows exactly what the answer does not know.

The same endpoint **refuses** at Melamchi, where the only higher ground is downhill and across the
water, and at Nepalgunj, where it is 4.8 km away. A refusal that says so beats a direction that is
wrong.

## What is deliberately NOT verified

Stated here so nobody has to find it:

- **Nothing has run on a real handset.** Every radio range figure — the 30 m Bluetooth hop, the
  300 m Wi-Fi Aware hop, the 3–4 km chain — is measured by other people or modelled from their
  measurements. The logic is tested; the radios are not.
- **No cryptographer has reviewed the sealing layer.** It uses vetted primitives correctly as
  far as the tests show, which is not an audit.
- **The client's sealing has never run in a browser.** It is verified by running the client's own
  JavaScript in node against the Python gateway, which is not the same thing.
- **Rainfall does not identify which slope fails.** This is measured, reported, and the reason the
  system ranks and routes rather than predicts — see [docs/LIMITATIONS.md](docs/LIMITATIONS.md).
