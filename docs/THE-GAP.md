# The gap the whole field leaves open

Researched on 2026-10-01, against GitHub's own index and the projects' own descriptions.

## What everyone else built

Every landslide and flood early-warning repository, ordered by interest:

```
  24★  SailabAlert               AI-powered flood & landslide early warning DASHBOARD for Pakistan
                                 "ML risk prediction + Groq-generated" - a web app, proprietary API
  25★  Early-Warning-System-for-Climate-Disasters        machine learning
   2★  AI-LandSlide-Early-Prediction                      "AI-powered landslide prediction", Nepal
   2★  GiriRaksha                                        "AI-powered landslide early prediction"
   2★  BhoomiRakshak                                     "AI-based early warning and risk monitoring"
   1★  Landslide-Risk-Prediction
   0★  CoastGuard-AI  (three separate copies)
   5★  flood-warning-system          "machine learning, real-time..."
   4★  AI---Flood-Prediction-Alert-System
```

**Seven of the ten are one thing:** collect rainfall, run a model, produce a risk number, draw it on a
map, put it on a web server. **The other three are copies of the first.**

## Three assumptions every one of them makes

1. **That the network is up.** They are web dashboards. The audience needs a browser and a connection.
2. **That a proprietary model is acceptable.** The leader's own description says *"Groq-generated"* - a
   hosted API, which this event explicitly discourages and which cannot run where the problem is.
3. **That the reader is an official.** The output is a risk score on a map, addressed to somebody with a
   dashboard open. **The person standing in the water is not the user.**

## And the thing the field is measuring is not the thing that kills people

Nepal's 2024 monsoon killed people **after warnings were issued.** The failure was not prediction - the
rainfall was known, the slopes were documented, the advisories existed. **The failure was delivery and
action:** the warning reached an office rather than a person, on a phone with no signal, at four in the
morning, in a village with one road out.

**So the field is optimising the part that already worked.** Prediction is not the bottleneck.
Everything downstream of the prediction is.

## What that leaves open

Five things that are true of this project and of nothing else in that list:

| | everyone else | this |
|---|---|---|
| **when the network is gone** | they stop | **it is built for that hour** |
| **who the output is for** | an official with a dashboard | **the person holding the phone** |
| **what it outputs** | a risk number | **which way, how high, and by when** |
| **who is accountable** | unaddressed | **a named office, under a named section of law** |
| **the model** | a hosted API | **open-weight, on the handset, no key** |

## The idea that no one in this field has built

**The warning that travels phone to phone when the towers are down.**

Every system above dies with the network. This project already has the only piece that survives it -
a **Bluetooth advertisement carrying a distress frame**, verified working on real hardware. What it does
not yet have is the **relay**: a phone that hears a warning and passes it on.

**With that, the mesh is the product.** A slope fails above a village. One phone knows. It has no signal.
**It advertises. A phone three hundred metres away hears it, keeps the message, and advertises it again.**
The warning crosses the valley without a single tower, and each phone is a node that costs nothing and
needs no infrastructure that a flood can wash away.

**Why this wins on the event's own criteria:**

- **innovation** - the field has no mesh; the field has no offline story at all
- **technical excellence** - a real BLE relay with hop limits, deduplication and a bounded flood, proven
  on hardware rather than described
- **real-world impact** - it addresses the exact failure that killed people in 2024: the warning existed
  and did not arrive
- **not the anti-pattern** - the radio is used by the loop, and the loop's output changes the world
- **and it cannot be copied from a dashboard**, because a dashboard is the thing it replaces

## What is already built toward it

- a Bluetooth frame codec with `ttl` and `hops` already in the payload
- **verified hardware advertising** - `dumpsys` confirms the handset as a GATT advertiser
- an escape planner that computes direction and height from the bundled elevation grid
- **the last safe minute** - the deadline, which is what makes a relayed warning actionable
- a routing engine that turns a warning into a letter addressed to the office obliged to act
- a provenance panel, so every number in a relayed message can be traced

**What is missing is one component:** a phone that scans, keeps what it hears, and advertises it onward.

## The sentence this produces

> **Every other project in this field is a dashboard that dies with the network. This one is a mesh that
> forms when the network dies - the slope tells one phone, and that phone tells the next, until the
> village knows which way to run and how long is left.**
