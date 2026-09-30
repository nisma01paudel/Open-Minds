# Demo video script — 2–3 minutes (mandatory submission item)

Recording notes: screen capture at 1080p, no talking head needed, large fonts. The whole critical path
runs **offline** — the model server and all data are local, because Demo Day is in person on unknown wifi.
Pre-warm the model before recording, and keep a cached run as a fallback.

---

### 0:00–0:25 — The problem, with a number nobody has published

**On screen:** the per-AOI clear-fraction table.

> "Nepal has world-class landslide science. Here is what it does not have. I measured eleven years of
> Sentinel-2 imagery over one slope in Dhading — 933 scenes. **In July, zero percent of them had more
> than eighty percent clear ground.** Not few. Zero. And July is when landslides kill people.
>
> So every optical monitoring system in the country is blind exactly when it matters."

### 0:25–0:50 — The real gap

**On screen:** OPML's 2020 recommendation, then BIPAD's citizen-report numbers.

> "But detection isn't the gap either. Nepal's government already recommended the missing piece in 2020 —
> overlaying rainfall watch with landslide susceptibility. It was never built.
>
> Meanwhile BIPAD has received **7,081 citizen hazard reports. Zero are verified.** Genuine ones sit
> there unactioned — 'सडकमा क्षति', damage to the road, filed forty-six times.
>
> **Nepal can detect. Nepal cannot dispatch.** That last metre is what we built."

### 0:50–1:40 — The product, running live

**On screen:** the terminal, in a large font. (There is no dashboard - the deliverable is the
command, the trace and the advisory. Nothing here should be shown that does not exist.)

> "A report arrives: *'a rural road built by a municipality on the slope above a national highway has
> failed and blocked the highway.'*"

Run: `./scripts/demo.sh`  (defaults to 2024-09-28, the day our benchmark records 167 landslides)

> "The system resolves the location from government geospatial data — **Ward 11, Thakre, Dhading**.
>
> Then the open-weight model triages it. Watch which asset it names as failing: **the municipal rural
> road — not the highway it damaged.** That distinction is the whole point, and it is the case that
> swept two buses carrying sixty-two people into the Trishuli at Simaltal in July 2024 - nineteen bodies
> recovered, forty never found. The fatal slope was a rural road built by Bharatpur Metropolitan City;
> the buses were on a federal national highway. Everyone was looking at the highway.
> (Sourced: `docs/research/nepal-slope-responsibility-map.md`, §4.3.)"

**On screen:** the Nepali advisory.

> "Out comes a Nepali advisory addressed to a named office under a cited section — Local Government
> Operation Act 2074, section 12(2)(c)(23), the ward's duty to remove landslides in roads — plus the
> escalation path and the register payload. The fields we cannot evidence are listed as
> **required from the office**, never invented."

### 1:40–2:10 — The honesty layer, and the distinction behind it

**On screen:** the same slope on a second date, verified to behave differently:
`./scripts/demo.sh --as-of 2024-07-20`

> "Now the part I am proudest of, and it is not a refusal - it is a distinction. Look at the first run
> again. The rain trigger was **exceeded**: a hundred and ninety millimetres in forty-eight hours against
> a hundred and forty-two. And the system still **refused to claim a detection**:
>
> *'वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन'* - the slope has been made
> sensitive by rainfall, but no recent observation is available. It calls its own output **a signal of
> risk, not a confirmation of it**, and still addresses it to the office that owns the asset.
>
> Now run the same slope in July, with no rain. Same blindness - the last usable optical look is
> twenty-seven days old, worse than September's twelve. And this time it issues **nothing at all**.
>
> That is the whole design. A system that abstains on both dates is useless. One that warns on both is
> crying wolf every cloudy day of the monsoon. This one separates *'this slope is primed and I cannot see
> it'* from *'nothing is raising this slope and I cannot see it'*."

### 2:10–2:40 — The differentiator: where to build instead

**On screen:** the siting line of the same advisory.

> "But look at the last two lines. Every existing Nepali slope tool stops at a colour on a map. A road
> office cannot act on a colour. This one says:
>
> *'सोही ठाउँमा मर्मत नगर्नुहोस् — नयाँ लाइन करिब १९५ मिटर माथि सार्नुहोस्, करिब ७५ मिटर उचाइ बढी।'*
>
> **Do not repair in place. Move the new line about 195 metres upslope and 75 metres higher.** It read that
> from the terrain — there is a 29-degree source zone 135 metres above the road — and it says the advice is
> a terrain screen requiring geotechnical verification, not a design."

### 2:40–3:20 — Evidence, then the ask

**On screen:** the ablation table and the E1 routing score.

> "This is measured, not asserted. Optical-only, the system can speak on **ninety point four percent** of
> days, with a hidden **thirty-four day silence** across the monsoon. Adding radar closes it - plus
> fifty-eight points in July, and the result replicates in a second, independent area.
>
> And I pushed that measurement further: a hundred and forty-two documented failure sites, two thousand
> and twenty-one scenes screened in the thirty days before each one. **A third of those scenes were
> usable. In August, a sixth.** Seventeen of those hundred and forty-two slopes - twelve percent - had
> **no usable look at all** in the month before they failed. Radar had a pass over every one of them.
>
> That is the honest scale of the blindness, and it is why the layer says so rather than going quiet.
>
> And on routing accuracy against twenty-one expert-labelled scenarios: **61.9% end to end, 76.2% on asset
> identification — with zero confident misroutes across road tiers and 100% abstention precision.** We got
> there by measuring, diagnosing and re-measuring: the first design scored 38.1% and never once abstained.
>
> The ontology, the harness and the data are open. Free data, no API keys, and an open-weight model that
> runs on a laptop. Every ward in Nepal could run this."

---

## Shot list

| # | Asset | Source |
|---|---|---|
| 1 | Per-AOI clear-fraction table | `reports/eval-v0.md` §1 |
| 2 | OPML recommendation + BIPAD counts | `docs/research/nepal-slope-reporting-chain.md` |
| 3 | Live end-to-end run, 7 tool calls | `./scripts/demo.sh` (2024-09-28, the default) |
| 4 | Nepali advisory, fully Nepali | the same run's output |
| 5 | `primed-unobserved`: trigger EXCEEDED, no detection claimed | the same run |
| 5b | **Full abstain**: trigger below, equally blind, nothing issued | `./scripts/demo.sh --as-of 2024-07-20` |
| 6 | **Siting recommendation** | `सिफारिस (स्थान)` line: 195 m upslope, +75 m |
| 7 | Ablation + gap table | `reports/eval-v1.md` |
| 8 | E1 routing score | `reports/routing-ablation.md` — 38.1% → 61.9%, three arms |

## Do not say

- Never "predict". Say **detect, rank, route, recommend**.
- Never claim we detect landslides better, or that we are first at anything except the cited routing key.
- Never present a routing result without its confidence and, where relevant, its `needs_review` marker.

---

## Presenter mode — the app drives the demo

The eight beats above are built into the app, so the presentation does not depend on
remembering URLs or fumbling between windows:

```
http://localhost:8100/?present=1        then  →  to advance,  ←  back,  Esc  to exit
```

The cue card sits at the bottom of the screen, under the visual the room is looking at.
Each beat sets the map state itself — live, a quiet week, the season running, the peak
day, the blind-spot line — and the last three open the 3D view, the phone view and the
film.

| # | Beat | What is on screen |
|---|---|---|
| 1 | The national picture | 613 slopes on real Sentinel-2 imagery, live |
| 2 | A quiet week | mid-June — **0** above threshold, 0 approaching, nothing loaded |
| 3 | The season, running | the 2024 monsoon plays across the country |
| 4 | The day — 28 September 2024 | 305 of 613 above threshold |
| 5 | And we could not see them | only 27.8% of September imagery had clear ground |
| 5b | Where we are blind | the observability layer — 142 measured sites, 17 never seen; August 16.8% |
| 6 | Fly over it (3D) | real elevation, real imagery, real rainfall |
| 7 | From the phone | a camera view of the slope you are standing near |
| 8 | Leave them something | the ten-second film, downloadable |

### Why this exists

The failure it prevents is not technical. It is standing in front of a room with five
minutes on the clock, switching between a map, a 3D scene, a phone and a video, and
losing thirty seconds each time. The beats are pre-set and the arrow keys are enough.

### If something breaks on the day

Every layer is keyless and the app is a PWA, so after one visit the whole thing runs with
the network unplugged. The film is a local file. The one thing that needs care is the
phone view: camera access requires HTTPS, so use `scripts/serve_https.py` — plain
`http://<lan-ip>` will serve the page and silently refuse the camera.
