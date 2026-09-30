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

**On screen:** terminal, then the dashboard.

> "A report arrives: *'a rural road built by a municipality on the slope above a national highway has
> failed and blocked the highway.'*"

Run: `python scripts/demo_end_to_end.py --report "..." --lon 85.0575 --lat 27.7620 --as-of 2024-07-20`

> "The system resolves the location from government geospatial data — **Ward 11, Thakre, Dhading**.
>
> Then the open-weight model triages it. Watch which asset it names as failing: **the municipal rural
> road — not the highway it damaged.** That distinction is the whole point, and it is the case that
> killed sixty-two people at Simaltal in July 2024, because the upslope road belonged to a municipality
> and everyone was looking at the highway."

**On screen:** the Nepali advisory.

> "Out comes a Nepali advisory addressed to a named office under a cited section — Local Government
> Operation Act 2074, section 12(2)(c)(23), the ward's duty to remove landslides in roads — plus the
> escalation path and the register payload. The fields we cannot evidence are listed as
> **required from the office**, never invented."

### 1:40–2:10 — The honesty layer

**On screen:** the same command at `--as-of 2024-09-28` — the day BIPAD records 167 landslides.

> "Now the part I am proudest of. Run it for the twenty-eighth of September, the day our benchmark records
> a hundred and sixty-seven landslides. The rain trigger is **exceeded** — a hundred and ninety millimetres
> in forty-eight hours against a hundred and forty-two.
>
> And the system **refuses to claim a detection**:
>
> *'वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन'* — the slope has been made
> sensitive by rainfall, but no recent observation is available. It says plainly that this is **a signal of
> risk, not a confirmation of it**.
>
> In July an optical system has nothing to show. Silence is indistinguishable from safety. This is the
> state no existing tool produces."

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

> "This is measured, not asserted. Optical-only, the system can speak on eighty-nine point six percent of
> days, with a hidden **thirty-four day silence** across the monsoon. Adding radar closes it — plus
> fifty-eight points in July.
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
| 3 | Live end-to-end run, 7 tool calls | `scripts/agent_demo.py --as-of 2024-09-28` |
| 4 | Nepali advisory, fully Nepali | `evidence/agent-2024-09-28-v4.log` |
| 5 | `primed-unobserved` state | the same run: trigger EXCEEDED, evidence abstained |
| 6 | **Siting recommendation** | `सिफारिस (स्थान)` line: 195 m upslope, +75 m |
| 7 | Ablation + gap table | `reports/eval-v1.md` |
| 8 | E1 routing score | `reports/routing-ablation.md` — 38.1% → 61.9%, three arms |

## Do not say

- Never "predict". Say **detect, rank, route, recommend**.
- Never claim we detect landslides better, or that we are first at anything except the cited routing key.
- Never present a routing result without its confidence and, where relevant, its `needs_review` marker.
