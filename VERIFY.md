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
