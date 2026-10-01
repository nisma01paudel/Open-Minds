# Limitations and future work

The guidelines ask for limitations and future improvements to be present and complete. This is that
list, and it is deliberately longer than the capabilities list.

## What this is not

- **Not validated for prediction.** Nothing here claims the system would have forecast any landslide.
  The retrospective work measures two narrower things: whether the evidence needed to say anything
  existed at all (observability), and whether the rainfall trigger fired. Those are preconditions, not
  forecasts.
- **Not a warning service.** It is a prototype on pilot areas. No operational skill claim is made.
- **Not a geotechnical design.** The siting recommendation is a terrain screen. Runout is not modelled,
  geology and drainage are not considered, and every recommendation requires a geotechnical assessment
  before any design or construction decision.
- **Not legal advice.** The routing key cites the provisions it relies on. A Nepal-based legal reviewer
  must check every row before operational use.

## Measured limits

| Limit | Value | Where |
|---|---|---|
| Optical-only days an advisory could be issued | 90.4% (2024) | `reports/eval-v1.md` |
| Longest optical blind streak | **34 days**, across the monsoon | `reports/eval-v1.md` |
| Scenes >80% clear in June / July / August | **0.0% / 0.0% / 0.0%** | `reports/eval-v1.md` |
| Routing exact-case accuracy | 61.9% (asset 76.2%) | `reports/routing-ablation.md` |
| Duty identification — the weak axis | 52.4% | `reports/routing-ablation.md` |
| Under-routes (abstained when routable) | 7 of 21 | `reports/routing-ablation.md` |
| Radar usability | **not yet measured** — confidence is capped and labelled | `docs/MODELS.md` |
| InSAR | not processed; LiCSAR coherence measured at **0.16**, too low to rely on | `docs/DATA.md` |

## The result that constrains what we may claim

**Rainfall load does not identify which slope fails.** We tested our own core assumption
against our own benchmark: on 2024-09-28 and 2024-07-07, the slopes that actually failed
ranked at the **55th and 53rd percentile** of the rainfall ranking — a coin toss. Of the 14
documented failures on the peak day, only **4** had crossed the threshold, and their median
load was *below* the median of all 613 slopes. Full method and table:
`reports/rainfall-ranking.md`.

So the national map is a list of slopes **under load**, with the office responsible for
each. It is **not** a prediction, it does not rank by likelihood of failure, and any
reading of it as a forecast is wrong. What the ranking does buy is regional priming —
"the ground across this district is loaded" — not a per-slope guess.

This is the third independent measurement pointing the same way, after the event-vs-control
test (+3 points) and the 2018-08-08 case (thirty-plus landslides on a 51 mm day against a
118.8 mm threshold).

## Honest gaps that no amount of engineering closes in four weeks

1. **Radar usability is assumed, not measured.** Acquisition times are known (4–6 passes a month);
   per-pixel usability on steep terrain is not. Every radar-derived confidence is therefore capped
   and labelled as an upper bound.
2. **Controls are weak evidence.** Absence of a recorded failure is not evidence of stability. Nepal's
   inventory is thin, so any false-alarm rate derived from `benchmark/controls.csv` is a **lower bound**.
3. **The rainfall field has given everything it has.** Per-slope evidence — radar change,
   terrain, citizen reports — is what would actually improve prioritisation, and that is
   where the next work goes. The rainfall layer cannot be tuned into it.
4. **The duty labels are debatable.** Maintenance versus emergency is genuinely ambiguous for a report
   like "a road above the highway has failed": the failing asset needs its owner, and an event has also
   occurred. Some of the measured routing error is label ambiguity, which is exactly why E2 reports
   inter-rater agreement rather than a single score.
4. **No prospective validation.** Nothing here has been tested against a future failure, and it cannot
   be within the challenge window.
5. **Nepali is templated, not generated.** A purpose-built 1B English–Nepali model scores at chance, so
   the model selects among human-reviewed sentences. The templating guarantees fluency and safety at the
   cost of range.
6. **One AOI for the satellite statistics.** Two, now: the result replicates across both, but neither is
   a national sample.
7. **The citizen-report path is designed but not wired.** BIPAD's citizen intake holds 7,081 reports of
   which zero are verified, so the design deliberately requires a named verifying authority before
   anything is written there. That workflow is specified, not built.
8. **No live integration with BIPAD or DoR.** The register payload is produced and validated; it is not
   submitted, and no agreement exists to submit it.

## Future work, in the order that would matter most

1. **Revive the GPU** (the RTX 4050 is present but stuck after suspend) and re-run E1 with a larger
   open-weight model. Duty identification is the axis most likely to move.
2. **Measure radar usability properly** — fix the Sentinel-1 geolocation trap with the annotation grid,
   then replace the upper bound with a measured figure.
3. **Second annotator for E2**, to separate model error from label ambiguity on the duty axis.
4. **Terrain-matched controls** using the DEM (elevation band, slope class, aspect) rather than distance
   alone, and expansion to COOLR, DesInventar and the two UNOSAT inventories for exclusion.
5. **Wire the citizen-report path** with the verification tiers the design specifies.
6. **Extend the routing key** beyond roads: schools and health posts are partly covered, and the
   private-land case has a genuine legal gap that no code can close.
7. **A Nepali-reading expert panel** to review every template line before any operational use.

## The film is older than the product

`reports/video/pahiro-narrated-web.mp4` is a required submission item and it was cut before the
daily-use half existed. It shows the disaster pipeline and the trip planner; it does **not** show the
3D flythrough, the walk planner or the field app.

**The stills directory is gitignored** (`reports/video/stills/`, "regenerable and stays ignored"), so
the film's inputs are not in the repository and neither are any additions to them. Extending the film
is a local build step, not a repository change, and a reader of this repository cannot tell from it
whether the film was ever extended.

### The film and its narration now agree

`cap cd` says "31 of 613 ... peaked the day before, at 149" and the narration for the same beat says
"छ सय तेह्र मध्ये एकतीस ढलानले वर्षाको थ्रेसहोल्ड नाघे। भोलिपल्ट सिजनको उच्च बिन्दु एक सय उनन्चास
पुग्यो।" The film was rebuilt and the audio re-recorded, so the spoken number and the on-screen number
match.

**How the re-recording was possible after the OmniVoice quota ran out:** the film's own wavs are
22,050 Hz, which is the local `evidence/voices/ne_NP-chitwan-medium.onnx` Piper voice. Synthesising an
UNCHANGED line with it reproduced the existing wav to within 2.5% of duration - the same model,
re-run - so the corrected line was recorded locally with the same voice.

    d.wav      9.x s  ->  12.23 s   (the corrected line names the peak, so it is longer)
    the film   156 s  ->  159 s     which is the evidence that the audio actually changed,
                                    not another rebuild that reused a cached wav

The duration moving by the amount the text grew is the check that the earlier silent no-op did not
repeat. `scripts/build_voiced_video.sh` still reuses `voice/<key>.wav` when it exists and still builds
a captioned SILENT beat when it does not - so any future narration change must delete the affected wav
first, or it will not be heard.

To extend it, three edits go together:

1. a `cap <letter> "<caption>"` line in `scripts/build_voiced_video.sh`
2. a matching `<letter>|Nepali text` line in `reports/video/voice/narration.txt`
3. an entry in the clip order

then rebuild, which re-synthesises the narration and re-encodes about three minutes.

The build **aborts if a clip is missing** rather than silently shortening the film, and the committed
film is restorable with `git checkout`, so a failed attempt is safe. Note that
`reports/video/stills/` already contains **two sets** numbered 07-09 - `07-agent`, `08-limit`,
`09-trails` and, locally, `07-fly`, `08-plan`, `09-field` - so the clip letters and the caption keys
must be chosen against the build script rather than against the filenames.
