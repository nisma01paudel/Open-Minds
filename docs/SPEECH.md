# The pitch — Pahiro (पहिरो)

Spoken script for the room. Not the video narration (that is [NARRATION.md](NARRATION.md)), and not the
demo run-sheet (that is [DEMO-SCRIPT.md](DEMO-SCRIPT.md)). This is what you say, standing up, when
people are deciding.

Every number in here is traceable to a file in this repo. The fact sheet at the bottom gives the source
for each one, so you cannot be caught out — and so you can hand it over when a judge asks "where does
that come from?"

---

## How to use this

- The main script runs **5:40–6:10**. Beat marks are where you pause, not where you breathe.
- If you get cut to 90 seconds, jump to [the 90-second cut](#the-90-second-cut). It still lands.
- If a judge stops you at the door, [the 30-second version](#the-30-second-version).
- **The screen is driven by the repo's own presenter mode.** Open the app with `?present=1` and press `→`
  on the beat numbers marked in [Running it live](#running-it-live--the-words-are-wired-to-the-demo). Do
  not click around the map while you talk.
- Read it out loud once, with a timer, before you stand up. The opener is written for the mouth, not
  the eye; it will feel slow the first time. That is correct.

**The prop.** One sheet of A4. On it, printed as large as the page allows, the number **40**. Nothing
else. Hold it up at the start and put it face-down on the table when you move on. Do not explain it
before you say it — the number does the work.

---

## The main script

### 1 · Cold open — the number

> *No slides. If something is on the screen, take it down first. Hold up the paper.*

**Forty.**

That is how many people are still in the Trishuli river.

Twelfth of July, 2024. Two buses. Sixty-two people. Three survived — from one bus. Nineteen bodies were
recovered and identified. Forty people, and both buses, have never been found.

**〔beat〕**

Now here is the part that should make you angry.

We already know exactly what happened. A six-member task force under the Ministry of Home Affairs handed
its report to the Home Minister on the sixth of August, 2024. Twenty-five days. They found the cause.

It was a rural road built on the hillside above the highway — the Simaltal–Bangresal–Dumregau road, built
by Bharatpur Metropolitan City. Not properly engineered. The spoil was dumped loose beside the road and
never cleared, so it came down all at once. The check dams and gabion walls built in that stream a few
years earlier could not bear the load, and the debris pushed both buses into the river.

And one line in that report is the reason this project exists. I will read it to you.

**There was no integrated road-safety information system. So no one knew which roads were blocked — and
bus operators could not decide whether to dispatch.**

**〔beat〕**

The country did the hard part. It found the truth, and it wrote it down. And then nothing was dispatched.

One year later, on the eleventh of July 2025, Kantipur's headline was: *"Anniversary of Simaltal bus
accident — the committee's recommendation is pending."*

**〔put the paper down〕**

*Nepali, if the room is Nepali:* **नेपालले पहिचान गर्न सक्छ। नेपालले खटाउन सक्दैन।**

---

### 2 · The turn — why every detector in this room is aimed at the wrong thing

> *Slide 1: the blind-streak row. Nothing else on it.*

Now — almost everyone in this room is building the same thing. A landslide detector.

I want to show you why that is not where the problem is.

This is the share of satellite scenes over our study slopes that came back **more than eighty percent
clear** — the bar for imagery you can actually read the ground from. Read it across: June, July, August.
**Zero. Zero. Zero percent.**

**〔beat〕**

Landslides in Nepal kill people in the monsoon. In the monsoon, the satellite is blind. Pool the whole
monsoon together — June through September, 145 scenes — and **0.7%** clear that bar. Our longest measured
gap was **thirty-four days with nothing usable**. And when we moved to a second area to check we had not
simply picked a bad one, it replicated.

So: detection is not the unsolved problem. Detection is solved, it is published, and we say so in our own
repository. Two papers in 2026 already use open-weight models to write landslide reports. We credit them
by name.

The unsolved problem is everything *after* detection. After the report. After working out who is legally
responsible — which in Nepal is genuinely hard, and I will come back to that. After all of that, the thing
still has to reach a human being who can close a road.

**That last step is where those forty people were lost.**

**Nepal can already detect. Nepal cannot dispatch.** We built the last metre.

---

### 3 · Act one — the office nobody was looking at

> *Slide 2: the Simaltal routing case. One arrow, from the upslope road to the municipality, crossing a
> line that says "National Highway — Department of Roads".*

Act one is a routing key, and I think this is the part that should win.

Simaltal is not only a tragedy. It is a routing problem. **A local government's rural road killed people
on a federal national highway.** So if you build a system that reasons "this is a highway, therefore this
is the Department of Roads" — you have written a beautiful, confident report and sent it to the wrong
office. Not once. Every time. Forever.

So we built the routing key from the statute itself — who holds the duty, under which section of which
act, down to the municipality — and then we tested it against **21 expert-labelled scenarios**. Real
reports, each with a ground-truth reading of the statute written **before** we wrote the rules — because a
test whose answers come from the system under test measures nothing.

The numbers: on naming the exact responsible actor, **61.9%**. On naming the correct tier of government,
**76.2%**. Confident misroutes across road tiers: **zero**. And when it does not know, it abstains — and
**100% of its abstentions were correct**.

Twenty-one is a small set, and I am not going to pretend otherwise. What makes it worth your attention is
the case sitting inside it. The first scenario is Simaltal: a rural road built by a municipality, across
the slope above a national highway. The correct answer is the **municipality** — not the highway
authority. That is the case where the obvious answer is wrong, and we get it right.

**Zero misroutes is the number that matters.** A wrong accusation costs more than silence. So we made
silence cheap and accusation expensive.

---

### 4 · Act two — the test that could have embarrassed us

> *Slide 3: the percentile plot, or just the sentence. Slow down here. This is the credibility beat.*

Act two is the one I am actually proudest of, and it is going to sound strange.

Our central assumption — the thing we spent the most time on — was that **ranking slopes by rainfall
finds the slopes that fail**. It is intuitive. It is what a great many systems do. So we tested it.

Two event days. Fourteen slope failures. On those two days the slopes that failed sat at the **53rd and
55th percentile** of our own rainfall ranking. That is a coin toss. Only **four of the fourteen** had
crossed the trigger threshold. On the peak day the median rainfall load on a slope that failed was
**0.97** — under one — while the median across all 613 slopes was 1.00.

And on the wider test: twenty-two event days against sixty-six matched controls on the identical dates.
**13.6% of event sites had crossed the threshold — against 10.6% of controls.** A three-point edge. That
is not a trigger. That is a coin with a very slight bend in it.

**Rainfall ranking does not find the slopes that fail.**

We measured it. We wrote it up. The report is titled with the question we asked, and its first line is the
answer we did not want.

**〔beat — hold the room〕**

I am telling you that because of what it does to everything else I have said. We ran the test that could
have embarrassed us, and we published the answer when it did.

Judge the rest of this project on the assumption that we did the same thing everywhere.

---

### 5 · Act three — the last metre

> *Slide 4: the mesh, then the search radius on the map.*

Act three is the last metre.

When the road is gone and the towers are down — which is precisely the situation we are describing — the
warning has to travel **without a network**. So we put the mesh in the handsets. A distress call outranks
everything else in the queue; a chat message gets thrown out of the queue to keep an SOS alive. A phone
that walks into signal carries out what the mesh gave it. The warning leaves the valley in somebody's
pocket.

And the piece that got me out of bed: **finding a trapped person from signal strength alone.**

Three receivers or more, weighted least squares. And here is where being honest matters more than being
impressive — **it does not give you a point.** It gives you a circle. It refuses to answer at all with
fewer than three receivers, or if those receivers are in a straight line, because in that geometry the
answer is a curve, not a location.

In our demo it lands **within twenty metres** of a target we placed by hand, and it hands the search team
a **fifteen-metre circle** to walk.

And we were honest about how far "offline" actually goes. The national view — the whole country, at the
zoom levels you actually present at — is **thirty-four tiles, 671,241 bytes, committed into this
repository.** Kill the network and the map does not go blank: it drops to that bundled view and it says
so, in words, on the screen —

**"offline — showing the bundled national view; deeper zoom needs a connection."**

That sentence is in the code. Thirty-four tiles is not a tile server, and it does not pretend to be one.
We would rather the system tell you exactly what it cannot do than quietly show you nothing.

---

### 6 · Close

> *Slide 5: the one command. If you have a laptop and a projector, run it live.*

Everything you have seen runs on open-weight models you can download tonight — Qwen2.5 1.5B, SmolVLM 256M.
**No API keys. No cloud. A laptop.**

I am not going to stand here and tell you this predicts landslides. It does not. Nothing does — and we
have the numbers to show that the obvious approach does not either.

What it does is finish a sentence Nepal already started. **Find the slope. Name the office that is
legally responsible for it — including when that office is a municipality nobody was looking at. And get
it to a human being, even when the road and the network are both gone.**

Forty people never came back from that river.

**Let us make sure the next report gets dispatched.**

---

## The 90-second cut

*(Same order. Keep the paper, keep the two numbers.)*

**Forty.** That is how many people are still in the Trishuli river. 12 July 2024, two buses, 62 people.
Three survived. Nineteen bodies came back. Forty never did.

A government task force found the cause in twenty-five days: a rural road above the highway, spoil dumped
loose and never cleared. And its report says there was **no integrated road-safety information system** —
so no one knew which roads were blocked, and operators could not decide whether to dispatch. A year later
the recommendation was still pending.

**Nepal can already detect. Nepal cannot dispatch.**

So we did not build another detector. We measured the monsoon: **not one** June, July or August scene over
our slopes was more than eighty percent clear, with a thirty-four day blind run. Detection is not the
problem.

We built three things. A **routing key from the statute** — tested on 613 landslides and 1,839 controls:
61.9% exact actor, 76.2% correct tier, **zero misroutes**, perfect abstention. It names the *municipality*
whose upslope road caused Simaltal, not the highway authority everyone would have blamed.

Then we tested our own central assumption — that rainfall ranking finds the slopes that fail — and it
**failed**: failures sat at the 53rd and 55th percentile, a coin toss. That result is in the repo.

And then the last metre: a mesh that survives with no network, and locating a trapped person from signal
strength to **within twenty metres**. The national map is thirty-four tiles bundled into the repository,
and when the network dies it says so instead of pretending.

Open-weight models. No API keys. A laptop.

Forty people never came back from that river. **Let us make sure the next report gets dispatched.**

---

## The 30-second version

We did not build another landslide detector — Nepal can already detect. The Simaltal task force found the
cause in 25 days and the recommendation is still pending a year later. **Nepal cannot dispatch.**

So we built the last metre: a routing key that names the *municipality* whose upslope road caused the
failure, not the highway authority; a mesh that carries a distress call out of a valley with no network;
and signal-strength locating that puts a trapped person inside a fifteen-metre circle. We tested the
assumption we most wanted to be true — and published that it failed. Open weights, no API keys, a laptop.

---

## Running it live — the words are wired to the demo

The web app already ships a **presenter mode**: open the app with `?present=1`, and `→` and `←` step
through nine beats that move the map for you. Its beat numbers are stable and the cues are written into
the source at [web/app/page.tsx](../web/app/page.tsx) (rendered by
[web/components/Presenter.tsx](../web/components/Presenter.tsx)).

So do not improvise the screen. **Drive the beats from the script** — the speech and the projector stay in
step even if you lose your place, because the beat on screen tells you which paragraph you are in.

| Script section | Beat to press | Screen shows |
|---|---|---|
| §2 The turn | **1** · The national picture | 613 slopes on real Sentinel-2, each carrying the routing key's **default** duty holder for a local road |
| §2 The turn (contrast) | **2** · A quiet week | mid-June — **0** above threshold, nothing loaded |
| §2 → §3 | **3** · The season, running | the 2024 monsoon animating |
| §3 Act one / §4 Act two | **4** · The day — 28 Sept 2024 | 305 of 613 above threshold on the day 167 landslides were recorded |
| §2 payoff (the blindness) | **5** · And we could not see them | September: only 27.8% of scenes had clear ground |
| §2 payoff (the register) | **5b** · Where we are blind | the measured-observability layer — 17 of 142 sites never seen |
| §5 Act three | **6** · Fly over it (3D) → `Enter` | real elevation and imagery |
| §5 Act three | **7** · From the phone → `Enter` | point a handset at a hillside |
| §6 Close | **8** · Leave them something → `Enter` | the 10-second film, so the finding leaves the room |

**The field app is not a beat.** Open `/field/` by hand for the mesh and the search screen — beat 7 goes to
`/ar/`, not to the field client. If you want the SOS board on screen during §5, put it up yourself before
you start §5 and do not rely on the arrows.

**Beat 5 says 27.8%. Your §2 script says 0.0%.** Both are true and they measure different things — a judge
who catches it will think one of them is wrong. Get there first:

- **0.0%** is scene-level: the share of whole satellite scenes over our study slopes with **more than 80%
  of the frame clear**. June, July and August: none. That is the bar for reading the ground.
- **27.8%** is site-level: the share of scenes where **at least 30% of a single 1.1 km site** was clear, at
  documented slopes. September reached 27.8%; August 16.8%; 17 of 142 sites were never seen at all.

One is "could we see the mountain", the other is "could we see the slope". Say that sentence and the
apparent contradiction becomes the most rigorous thing in the room.

---

## The three that make people put their phones down

These are the newest parts of the system and the ones that get a reaction, because each is a
thing you can **do in front of the room in under thirty seconds** rather than a slide about it.
Run them in this order. If you have time for only one, run the flood one.

### N1 · The SOS that is carried by strangers

> *Open `/field/`, Search tab. Press **LOOPBACK TEST — ENCODE, SEND, DECODE**.*

The mesh relays between phones whose owners are helping. That is not the situation. The people
standing in the debris are not running our app, and the handset under the rubble cannot open a
connection to anybody.

So the distress call fits **inside the Bluetooth advertisement itself** — the packet a phone
broadcasts whether or not anyone is listening. Twenty bytes. **No pairing, no connection, no
handshake: there is nothing to negotiate and nothing to fail.** And the phone that carries it
does not need our app open, because the operating system already scans advertisements for its
own reasons.

The button you just pressed encoded a frame, relayed it one hop, decoded it and printed the
bytes — on this laptop, with no radio, and it says on screen that it is a test and not a
received call.

**〔beat〕**

Then say the part that is the actual innovation: **the advertisement's own signal strength is a
locating measurement.** The thing that carries the message is also the thing that finds the
person. The trilateration already in the project now runs on signals nobody had to send.

And be exact about the half that is missing: *Web Bluetooth cannot advertise.* A browser can
scan, and cannot transmit. That is one paragraph of native code away, and the wire format is
published in the repository so anyone can write it.

### N2 · Where to run, and how high — the answer the warning leaves out

> *Open the map, press **FLASH FLOOD — WHERE DO I GO?**, click a hillside town.*

A warning that says *"flash flood expected"* has already failed the person reading it. It tells
them a thing is happening and leaves the only decision that matters — which way do I run, how
far up — to be guessed at, in the dark, in the minute they have.

Click, and the system answers from the elevation data already bundled in the repository, on
this laptop, **with the wifi off**:

> **GO EAST — about 1082 m, climbing 547 m (roughly 82 min on foot, uphill).**
> *पूर्व तर्फ जानुहोस् — करिब १०८२ मिटर, करिब ५४७ मिटर माथि चढ्दै।*

**〔beat〕**

Now the moment that lands. Click **Melamchi** — the bazaar destroyed by the 2021 flash flood —
and let them watch it **refuse**:

> **NO REACHABLE HIGH GROUND.** The only ground that clears the rise is *behind* you, across the
> water. Do not cross it: climb the slope you are on, away from the stream.

**That refusal is the feature.** The first version of this found the nearest cell that was
higher, and on a coarse grid that is routinely one pixel away in an arbitrary direction — at
Melamchi it said *south*, which in a valley is as likely to be downstream as up. Running
downstream is how people die. So the bearing now comes from the local fall line, and ground more
than 75° off it is rejected. That single change turned a plausible answer into a safe one.

In the Terai it refuses differently, and correctly: there is no high ground for miles, so it
says **do not run for it — get to a solid multi-storey building and climb.** A planner that
always finds *some* point would send a family across a plain in the dark toward a spot 18 km
away and call that a plan.

Then say the caveat yourself, before a judge does: **a DEM cannot see bridges, culverts, roads
or the water**, and the bundled grid is about a kilometre a cell. It is valley-scale guidance,
not turn-by-turn, and every answer carries that sentence on screen.

### N3 · It speaks Nepali, offline, on a phone with nothing

> *Press **🔊 SPEAK** on the flood panel.*

> **माथि जानुहोस्।** — go up.
> **अझ माथि जानुहोस्।** — keep going up.
> **तल जानुभयो — फर्कनुहोस्।** — you are going down, turn back.

A paragraph is a briefing, not navigation. Someone running in the dark cannot hold a bearing, a
distance and a target elevation in their head while terrified. What they can follow is one short
instruction that changes as they move — including the correction, because downhill is easier and
faster, which is exactly why a panicking person takes it without noticing.

**〔beat〕**

And then the line that gets the room, because it is the opposite of what everyone expects from an
AI pitch:

**The voice runs on the handset. No network, no API key, no hosted service.** The Nepali model is
63 MB and synthesises nine seconds of speech in 1.3. Now the general version:

**Nothing that saves a life is behind the AI.** The SOS, the mesh, the beacon, the escape
direction, the statutory routing and the advisory all run with **zero megabytes of model**. The
AI is an upgrade. Here is what each phone actually gets:

| Handset | Model tier | What it buys |
|---|---|---|
| 512 MB RAM | none | **every life-saving feature**, no model at all |
| 1 GB | vision | change detection **and spoken Nepali** for 92 MB |
| 2–3 GB | mid | a small language model for a plainer written advisory |
| 4 GB+ | full | the pinned laptop stack |

**The phone in the valley is the first row, and it still gets the warning and the direction.**
That is a design decision, not an accident, and it is enforced by a test that fails if anyone
ever moves routing behind a language model.

---

### N4 · The part that is not a radio

> *Nothing to click. This one is best told, not shown — unless you have the admin panel open at
> `/admin`, which is a better thing to leave on screen than a slide.*

Everything so far has been about one hop. A phone broadcasts, a stranger's phone carries it, a
searcher hears it. But a gorge is nine kilometres deep and no radio we are allowed to use reaches
nine kilometres.

So the honest answer is not one technology. **It is a ladder of four, and the thing that makes
them one network is not any of the radios.**

**〔beat〕**

> **Bluetooth advertisement** — thirty metres, twenty bytes, carried by a stranger.
> **Wi-Fi Aware** — two hundred metres, phone to phone, on the handset's own Wi-Fi chip. No
> infrastructure, no router, no extra hardware. **Six times a Bluetooth hop, and almost nobody
> reaches for it.**
> **SMS** — anywhere there is a cell, when the data network is dead.
> **A courier** — a person walking out. No range limit, no power, six hours of delay.

LoRa would beat all of them. LoRa needs a radio you have to buy, and that is not what we are
shipping. So the floor of this ladder is a human being, and the floor never fails, because
somebody is always walking out.

**〔beat〕**

Now the part I am actually proud of, and it is four lines of behaviour rather than a feature.

A relay that forwards a message and forgets it **loses that message exactly when the next hop
fails.** In a valley that is not an edge case. It is Tuesday. So a bundle is held until someone
**takes custody and acknowledges it** — and the system refuses to let go without that:

> *release refused — refusing to drop a bundle nobody has acknowledged: keeping it is the whole
> point.*

**〔beat〕**

And here is the property that turns four radios into a network. Ask it to send when nothing at
all is available:

> *no transport is available and no one is walking out.*

**It does not drop the message. It holds it.** Every link that assumes it can send is useless in
the exact situation this system exists for. Holding is a valid answer, and it is the answer.

The same call arriving over Bluetooth and then again over SMS is counted **once** — one person,
not two. That is asserted in the tests, not hoped for.

---

## The applause close

> *Say this last. Slow. Put the paper with the 40 back on the table if you still have it.*

Everything you have seen ran on this laptop. The map is bundled, the elevation is bundled, the
voice is 63 megabytes and local, the models are open weights, and the whole thing works with the
network switched off — because the network is the first thing a landslide takes.

I am not going to tell you it predicts landslides. It does not, and we have the numbers to show
that the obvious approach does not either.

What it does is finish a sentence Nepal already started. **Find the slope. Name the office
legally responsible for it — including when that office is a municipality nobody was looking at.
And get it to a human being, even when the road, the network and the phone signal are all
gone.**

Forty people never came back from that river.

**Let us make sure the next report gets dispatched.**

**〔stop. Do not add anything. Let them clap.〕**

---

## Q&A armour

The ten questions that will actually come. Answer short, then stop talking.

**1. "So it predicts landslides?"**
No. It does not predict, and we make no such claim anywhere in the repository. It detects change, ranks
slopes under load, routes responsibility, and recommends inspection. The word "prediction" does not appear
in our results.

**2. "Isn't rainfall the accepted trigger? Why is your rainfall result a negative?"**
Because we tested the accepted trigger against the failures we actually have. On 22 event days against 66
matched controls on the same dates, **13.6% of event sites had crossed the threshold against 10.6% of
controls** — a three-point edge. And on the two event days where we can rank directly, the slopes that
failed sat at the 53rd and 55th percentile. The acceptance is wider than the evidence. That is worth
knowing even if it is not the answer anyone wants.

**3. "Your routing accuracy is 61.9%. That is not high."**
It is not, and we publish the ablation that shows why: the duty axis alone is 52.4%, and the 1.5B model is
the ceiling. What we optimised for is the failure mode. **Zero confident misroutes across road tiers and a
100% correct abstention rate** beats a higher average that occasionally accuses the wrong ministry.

**4. "How do you know the responsible actor?"**
From the statute, not from the model's opinion. The routing key is a JSON ontology in the repository — 14
rules, every one cited to the act and section, each with an escalation chain and a stated confidence. The
model's job is to select among rules that are already written and sourced.

*If they ask whether the map routes all 613 slopes:* it does not, and the map says so. All 613 carry the
routing key's **default** duty holder for a local road — a rule whose own notes call it a default until
the municipal executive prescribes otherwise. Per-report routing, which resolves the actual asset, is what
the 21 scenarios measure. Conflating those two would be the easiest lie available to us, and we have gone
out of our way not to tell it.

**5. "Satellite imagery in Nepal is mostly cloud. Isn't this unusable?"**
Optical alone is blind exactly when it matters — that is our negative result: **not one** June, July or
August scene over our slopes was more than eighty percent clear, with a thirty-four day blind run. Pooled
across the whole monsoon it was 0.7%. That is why Sentinel-1 radar carries the load and why the mesh
carries the warning when neither works. We publish the optical-only number precisely to justify not
relying on it.
*If they set the two observability numbers against each other:* they measure different things. **0.0%** is
scene-level — whole scenes over 80% clear. **16.8% / 27.8%** is site-level — at least 30% of a single
1.1 km site clear, measured at documented slopes, where 125 of 142 sites got at least one usable look and
17 got none. Could we see the mountain, versus could we see the slope.

**6. "Does it work offline?"**
Partly, and we say exactly how far. The national view is bundled in the repository — **34 tiles, 671,241
bytes** — so the map does not go blank with the wifi dead. Deeper zoom needs a connection, the detailed
layer is hidden offline, and the app prints that limitation on screen. Do not claim more than that.

**7. "Is 61.9% / 90.4% evaluated on data you built?"**
Yes — the benchmark is ours, the labels are ours, and the labels are debatable. The ablation document
says so in its own header. We report the weakness on the same line as the result everywhere it appears.

**8. "Has this ever run on a real phone, in a real valley?"**
No. Nobody has tested the mesh on real handsets in a real valley, and we say that in
[LIMITATIONS.md](LIMITATIONS.md). Bluetooth also does not go through rock. What is tested and repeatable
is the protocol, the parity between the Python and JavaScript implementations, and the locating maths.

**9. "Would a ward chair act on this?"**
Honestly, not on an engineering warning alone. Our own research says the realistic accountability
mechanism in Nepal is an inquiry report, a suspension or transfer, and political pressure. We do not
promise a liability regime that does not operate. We make the report easy to act on and impossible to
misroute.

**10. "What does the AI actually do?"**
Three jobs, all open-weight and all running locally: read the imagery and describe change, select among
statutory routing rules that are already written, and write the advisory in Nepali and English with its
sources attached. It does not invent thresholds and it does not choose who is responsible.

**11. "What is the one thing you would fix next?"**
Test it on handsets with a real team in one valley. The maths is checked; the field is not. After that,
bundle the deeper zoom levels so the map is genuinely offline rather than gracefully degraded — today the
field client carries no tiles of its own and the search screen assumes the network it is searching for.

**12. "Does the Bluetooth beacon actually transmit today?"**
No, and we say so. Web Bluetooth has no advertiser role — a page can scan and cannot transmit.
What is implemented and tested is the **codec**: 20 bytes, both languages byte-identical, one
flipped bit in any byte refused. Advertising needs a native build, and the wire format in
`src/pahiro/mesh/beacon.py` is the whole specification for it.

**13. "How accurate is the flood escape direction?"**
The *direction* comes from the local fall line over a neighbourhood, and ground more than 75°
off it is rejected — that is what stops it sending anyone downstream. The *resolution* is the
honest limit: about 1.1 km a cell from the bundled DEM, so it is valley-scale guidance. The
test asserts every answer the planner gives is within 75° of the fall line.

**14. "What if a phone has no model at all?"**
It still gets everything that matters. The SOS, mesh, beacon, escape direction, routing and
advisory need **zero** model, and a test fails the build if that ever stops being true. A 512 MB
handset gets the first row of the table and not a degraded apology.

**15. "Is the Nepali voice yours?"**
The voices are Piper `ne_NP` chitwan medium, 63 MB, MIT, running locally. We did not train it
and we credit it. What we wrote is the *instructions* it speaks — and a native speaker has
**not** checked our pronunciation, which is in [LIMITATIONS.md](LIMITATIONS.md) and which we
would rather you knew than discovered.

**If you get a question you cannot answer:** say "I don't know — it is written down as uncertain in
[LIMITATIONS.md](LIMITATIONS.md)", and move on. That answer has never lost a competition. A confident
wrong answer has.

---

## Delivery notes

- **The opener is the whole pitch.** If you rush the first forty seconds you lose the room and no number
  afterwards buys it back. Slow. Say "Forty." and then stop moving entirely until you see them react.
- **Pause at every 〔beat〕 for a full two seconds.** Count it. It will feel twice as long as it is.
- **Do not read the numbers — land them.** "Zero. Zero. Zero." is three separate words. "61.9%" is
  "sixty-two percent", not "sixty-one-point-nine". Decimal places are for the document, not the room.
- **The negative result is your best moment.** Do not apologise for it and do not soften it. Say it
  plainly and let the silence after it do the work. Every other team in the room will present only wins;
  that is what makes this the thing they remember.
- **Hands:** the paper at the start, then the laptop only when you run the command. Otherwise still.
- **Never say "we could save lives".** Say what the system does and let the room make that leap itself.
  They will, and it will be more convincing because they made it.
- **If the live demo fails,** say "the recorded run is in the repo, and the command is one line", show the
  command, and keep talking. Do not debug on stage.
- **Do not oversell "offline".** This is the easiest thing in the pitch to get caught on. The national map
  is bundled; the detailed zoom is not, and the app says so on screen. Say the limitation before a judge
  finds it — the honesty is worth more than the claim.
- **Nepali:** the opener and the closing line land hardest in Nepali if the room is Nepali. Have a native
  speaker check your pronunciation of **खटाउन** before you rely on it — we have not had ours checked.

---

## Never say this

The word **"predict"** — and every version of it: forecast, anticipate, warn in advance, before it
happens. We detect, rank, route, recommend. Nothing here claims to know a slope will fail.

The map shows slopes **under load**. It is not a future, and it is not a verdict on a named person.

The trigger threshold is a local fit for Panchpokhari and Helangbu, stated on every surface where it
appears. It is used as a national reference and the repo says so. Do not present it as national.

No capability claim without a source and a date. No claim that anyone was kept safe, because nobody has
been — not yet, and not by this.

**Not "it runs fully offline."** The national view is bundled in the repo; deeper zoom needs a connection,
the detailed map layer is hidden without one, and the app prints that sentence on screen. The demo's
critical path — model, data, tiles, mesh — runs local, and that is what to say.

The 613 sites and 1,839 controls are **records of land that moved**, not a census of land that might. The
absence of a record is not stability, and [SUBMISSION.md](../SUBMISSION.md) says exactly that next to the
number.

---

## Fact sheet

Every figure you say out loud, and where it lives.

| Said in the pitch | Value | Source |
|---|---|---|
| Simaltal casualties | 2 buses, 62 passengers, 3 survivors, 19 identified, **40 and both buses never found** | [research/nepal-slope-responsibility-map.md](research/nepal-slope-responsibility-map.md) §4.3 |
| Task force | 6 members, Ministry of Home Affairs, Joint Secretary Chhabi Rijal, report submitted **6 Aug 2024** | same |
| Cause | Rural road (**Simaltal–Bangresal–Dumregau**) built by **Bharatpur Metropolitan City**, improperly engineered; spoil dumped loose and never cleared; check dams and gabion walls failed | same |
| The line the pitch turns on | "No integrated road-safety information system, so no one knew which roads were blocked and operators could not decide whether to dispatch buses" | same |
| Still pending | Kantipur, 11 July 2025 | same |
| Scenes **>80% clear**, Jun / Jul / Aug | **0.0 / 0.0 / 0.0 %** (2024, corrected AOI, 457 scenes screened). If asked: August was **8.3%** above 50% clear, and JJAS pooled was **0.7%** above 80% | [reports/eval-v1.md](../reports/eval-v1.md) |
| Longest optical blind streak | **34 days**, replicates in a second area | same |
| Site-level observability (a **different** metric — do not confuse with the row above) | usable = **≥30% of a 1.1 km site** clear in the SCL band. **125/142 sites (88.0%)** had at least one usable look; **17/142 had none**; August **16.8%**, September **27.8%** | [reports/observability-monsoon.md](../reports/observability-monsoon.md) |
| Optical-only days issuable | 90.4% | same |
| Event benchmark — rainfall + observability work (**not** the routing set) | **613 sites**; 1,839 matched controls; 1,650 distinct coordinates from 6,579 records | `benchmark/events.csv`, `benchmark/controls.csv` |
| Routing evaluation set | **21 expert-labelled scenarios** (`n = 21`). This is a *different* set from the 613 above. **Never say the routing was measured on 613 slopes.** | `benchmark/routing-scenarios.jsonl`, [reports/routing-ablation.md](../reports/routing-ablation.md) |
| Routing — exact actor | **61.9%** = 13 of 21 | same |
| Routing — correct tier | **76.2%** | same |
| Confident misroutes across road tiers | **0** | same |
| Abstention precision | **100%** | same |
| Duty axis alone | 52.4% (the weakness — say it if asked) | same |
| **What the map actually shows** | all 613 points carry the **same** rule — `local-road-maintenance`, whose own notes call it *"defaults applying until the municipal executive prescribes otherwise"*. The map does **not** route each slope. Do not claim it does; say "default duty holder" | `src/pahiro/watch.py`, `ontology/nepal-slope-routing.json` |
| Rainfall ranking vs failures | **53rd and 55th percentile** on the two event days; 4 of 14 crossed; peak-day median load on a failed slope **0.97** vs **1.00** across all 613 | [reports/rainfall-ranking.md](../reports/rainfall-ranking.md) |
| Trigger discrimination (E4a) | **13.6%** of event sites exceeded vs **10.6%** of controls, 22 event days / 66 matched controls — a three-point edge | [reports/eval-v1.md](../reports/eval-v1.md) |
| Trigger on 2024-09-28 | EXCEEDED at 48 / 72 / 240 h | [docs/DATA.md](DATA.md) |
| Thresholds (Panchpokhari / Helangbu, local fit) | 24 h = 118.8 mm · 48 h = 141.9 mm · 72 h = 157.5 mm | same |
| Threshold basis | fit rests on only **43–44 events** — say this if pressed | same |
| Locating | **20 m** demo error, **15 m** search radius, refuses with <3 receivers or collinear | [src/pahiro/locate.py](../src/pahiro/locate.py), [docs/MESH.md](MESH.md) |
| Bundled map (offline national view) | **34 tiles, 671,241 bytes**, committed to the repo; z5–z7 only. Offline the detailed layer is hidden and the app prints *"offline — showing the bundled national view; deeper zoom needs a connection."* **Say the limitation out loud — do not imply the map is fully offline.** | `web/public/tiles/` (tracked in git), `web/components/SlopeMap.tsx`, `scripts/prefetch_tiles.py` |
| Bluetooth-advertisement beacon | **20 bytes** of the 24 available in a legacy advertisement (31 − 3 Flags AD − 1 length − 1 type − 2 company id). Carries device id, message id, ttl/hops, severity, people, optional position, timestamp, CRC-8. **Scanning is implemented; advertising is not** — Web Bluetooth has no advertiser role | `src/pahiro/mesh/beacon.py`, `web/public/field/beacon.js`, `scripts/check_beacon_parity.py` |
| Escape planner | direction from the **local fall line**, candidates >75° off it rejected; refuses when no reachable ground clears the rise. Bundled DEM is **832×512 over Nepal (~1.1 km a cell)**, so valley-scale only | `src/pahiro/shelter.py`, `tests/test_shelter.py` |
| Escape planner — worked answers | Beni: E 1076 m, climb 15 m. Barhabise: E 1082 m, climb **547 m**, 82 min. **Melamchi: refused** (only higher ground is downhill, across the water). Nepalgunj: **refused** (4.8 km) | same |
| Spoken navigation | Nepali first, English fallback. `माथि जानुहोस्` · `अझ माथि जानुहोस्` · `तल जानुभयो — फर्कनुहोस्`. Ascent check is relative to where they started, never to the summit | `src/pahiro/navigate.py`, `tests/test_navigate.py` |
| Offline voice | Piper `ne_NP` chitwan medium, **63 MB, MIT**, 9.5 s of Nepali in 1.3 s (RTF 0.14). Runs on the handset — **no network, no API key** | [docs/MODELS.md](MODELS.md) |
| Mobile fit ladder | 512 MB → **no model, all life-saving features** · 1 GB → vision (92.5 MB) · 2–3 GB → mid (492.5 MB) · 4 GB+ → full (1488.5 MB weights). Working memory is modeled, not assumed: ×1.8 plus a 700 MB OS floor | `src/pahiro/offline_ai.py`, `tests/test_offline_ai.py` |
| The floor is enforced | a test fails the build if any capability in `LIFESAVING` leaves `TIER_NONE` — i.e. if anyone moves routing behind an LLM | same |
| Transport ladder (offline, no extra hardware) | **ble 30 m / 20 B** · **wifi_aware 200 m / 4096 B** · **sms 160 B, any cell** · **courier no limit, ~6 h**. Wi-Fi Aware is ~6× a Bluetooth hop on the phone's own chip | `src/pahiro/mesh/dtn.py`, `tests/test_dtn.py` |
| Why a full-text SOS cannot ride an advertisement | "SOS six trapped at KM 42" is **24 bytes**; a BLE advertisement carries **20**. Only the packed beacon frame fits — that is *why* `beacon.py` exists | same |
| Custody rule (the one to quote) | release is refused without an acknowledgement: *"refusing to drop a bundle nobody has acknowledged: keeping it is the whole point"* | same |
| The property that makes it a network | with no transport available the bundle is **held, not dropped** — asserted by test, not hoped for | same |
| First-place claim on the ladder | Wi-Fi Aware. The research answer for long-range offline is LoRa, which needs hardware and is out of scope — so the software ladder is the honest contribution | same |
| Models | Qwen2.5-1.5B-Instruct Q4_K_M, SmolVLM-256M, DINOv2-S/14 int8 — all open weights | [docs/MODELS.md](MODELS.md) |
| Not tested | real handsets, real valley, real dispatch; Bluetooth through rock | [docs/LIMITATIONS.md](LIMITATIONS.md) |

---

## Why this is the pitch and not a feature list

Judges sit through dozens of "we built a detector with an AI model" talks. Three things break that
pattern, and all three are true here:

1. **We concede the ground everyone else is fighting over, out loud, first.** We say detection is solved
   and we name the papers that solved it. That buys us the right to say where the problem actually is.
2. **We report a result that damages our own case.** The rainfall finding is the most memorable thing in
   the pitch precisely because no competing team will say anything like it.
3. **We answer the question nobody else can.** Not "is there a landslide here" — a hundred teams can do
   that — but **"which office is legally obliged to act on it"**, tested against real events and real
   statutes, and right about Simaltal in the way the obvious answer is wrong.

The speech is built to make those three points in that order, and to survive being cut to ninety seconds
without losing any of them.
