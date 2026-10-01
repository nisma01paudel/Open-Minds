# Where an agent actually belongs in this project

A strategy note, and it starts by throwing most of the obvious ideas away.

## What the event rewards, in its own words

Read off the event's own bundle rather than guessed at (see `docs/COMPETITION.md` for the source):

> The project that stands out for **innovation, technical excellence, open-source contribution, and
> real-world impact.**

And two sentences that decide this question:

> **Build with AI** — AI does real work inside the solution: processing, transforming, or reasoning over
> data as part of the system's core logic — **not just generating a response that gets shown to a user.**

> **The anti-pattern:** *Building a reusable skill, prompt library, or tool definition, **with nothing
> using it**.*

**That second sentence is a description of the average hackathon AI feature.** A chat box bolted to a
map is exactly "a response shown to a user". It cannot win this event, and building one would spend the
remaining time making the project more ordinary.

## So: what makes something an agent rather than a model call?

Three properties, and a feature needs all three to be worth the name:

1. **A loop** — it decides when to run, or when to run again, rather than answering when asked.
2. **Tools with consequences** — its output changes something outside the conversation.
3. **Autonomy worth trusting** — it acts when nobody is watching, and shows its reasoning afterwards.

A model call has none. A chatbot has none. **An agent that files a complaint has all three.**

## Where this project is unusually well placed

Most teams would have to invent the ground truth. This project already has the hard parts:

| already built | why an agent needs it |
|---|---|
| **613 documented slopes** with a rainfall series | a real, finite, checkable world to reason over |
| **CHIRPS daily rainfall** + Sentinel-2 metadata | the two signals a watch agent would actually read |
| **A routing engine that maps (asset, hazard) → the office obliged to act** | **a tool with a real consequence** |
| **The statute for each duty** (`LGOA 2074 s.12(2)(c)(23)`) | the agent cannot invent an institution — it reads one |
| **A provenance panel** where every number names its source | the agent's reasoning can be *checked*, not trusted |
| **Offline, open-weight models** (Qwen, SmolVLM, DINOv2) | it runs where the problem is, with no API key |

**The routing engine is the asset.** It is what turns a language model from something that writes
sentences into something that can **address a complaint to a named office under a named section of
law.** That is a tool with consequences, and it exists.

## Three candidate agents, ranked

### 1. The monsoon watch agent — recommended

**What it does, unattended, every morning of the monsoon:**

    read the last 24h of CHIRPS rainfall for all 613 slopes
    cross it against each slope's threshold
    for every slope that crossed: retrieve the routing key, resolve the office, read the duty
    draft the advisory in Nepali and English
    draft the complaint letter, addressed and cited
    write a dated log of what it decided and why, including what it could NOT see

**Why it wins on the event's own terms:**

- **"Real work as core logic"** — it produces a letter and an advisory, not a paragraph on a screen
- **"Real-world impact"** — it runs on days nobody opens the app, which is the whole point of a watch
- **Not the anti-pattern** — every tool it calls is used by the loop itself
- **Verifiable** — each day's log is an artifact, and every sentence in it traces to a source through
  the provenance machinery that already exists

**The honest limit, stated in the product:** it drafts. A human sends. *An agent that files a legal
complaint on its own is a liability, not a feature.*

### 2. The self-auditing agent — the most unusual

**What it does:** this project's own discipline, turned into a loop. It reads every claim in the repo —
every number in every document — checks it against the data file it came from, and files an issue when
one has drifted.

**Why it is interesting:** the event's anti-pattern is an artefact that nothing uses. **This agent's
job is to find artefacts nothing uses.** It would run against the project itself and report on it. That
is a genuinely novel thing to demo: *the project that checks its own homework, out loud.*

**Why it is second:** it is a tool for maintainers, not for the people in the flood. It scores on
innovation and technical excellence, and less on real-world impact.

### 3. The field agent on the handset — the most impressive, the riskiest

**What it does:** on the phone, offline. Reads the camera, the elevation grid, the compass and the
rainfall history, and decides what to tell the person holding it — including **refusing** when there is
no safe high ground.

**Why it is third:** the pieces exist, but a real on-device agent loop is a large build, and the
deadline is 30 October. **Its best parts are already in the app** — the escape planner refuses, the
provenance panel explains, the beacon transmits. The agent wrapper is the smaller half of the work and
the larger half of the risk.

## What I would cut, and why

**Not building these, deliberately:**

- **A general chatbot over the app.** The event names this as the failure mode.
- **The tourism features from the reference app** — fair pricing, travel buddy, AI guide vision. They
  need accounts and a server, they have no Nepali-disaster use, and porting them would dilute the one
  claim this project can defend: *it is the only entry built for the hours when the network is gone.*
- **Copying the reference repo's photographs** into this submission. They are another team's assets.

## The plan, if this is agreed

1. **Build the monsoon watch loop** as a runnable command with a dated log, on real data, for a real
   past monsoon — so the demo is a replay of days that actually happened, not a mock.
2. **Give it the routing engine as its tool**, so its output is a letter addressed to a real office
   under a real section of law.
3. **Make it refuse**: on days when the satellite could not see, it says so, and says what that means.
4. **Publish the log as an artifact** in the repo, and let the provenance panel explain every figure
   in it.
5. **Demo it live**: hand it the 2024 monsoon and let it walk through the days that killed people.

## The one-line pitch this produces

> **An agent that watches Nepal's slopes every morning of the monsoon, decides which ones have crossed,
> and writes the letter that names the office legally obliged to act — and says plainly on the days it
> could not see.**
