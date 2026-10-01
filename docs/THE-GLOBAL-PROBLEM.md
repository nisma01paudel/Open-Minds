# The global problem, and the one thing nobody has built for it

I was solving Nepal. The problem is not Nepali.

## The number

**3.5 billion people have no early warning system.** That is the UN's own figure behind *Early Warnings
for All*, whose target year is 2027 and which is not on track. Every flood, cyclone, tsunami, wildfire,
heatwave and landslide in that gap shares one shape:

> **The forecast exists. The warning does not arrive.**

This is not a prediction problem and has not been for twenty years. Global models know where the water
goes. The failure is always the same: **the last mile.** The warning is issued to an institution, on a
web dashboard, over a network that the disaster is in the process of destroying.

## Why every existing answer fails the same way

Every early-warning product — commercial, humanitarian, hackathon — is built on four assumptions:

1. **The network is up.** They are dashboards and apps. The disaster takes the network down first.
2. **There is someone to read it.** The output is a risk score addressed to an official.
3. **There is a server somewhere.** Compute is centralised, so the system has a single point of failure
   that sits inside the flood zone.
4. **The phone is a screen.** It displays what the server decided.

**All four assumptions break at exactly the moment the system is needed.** That is not a bug in any one
product. It is the architecture of the entire field.

## The inversion nobody has made

Here is the thing that has been sitting in plain sight:

> **The phone is the only computer 5 billion people own. There are more phones in a flood zone than
> there are people who will receive a warning. And a phone has a radio that does not depend on any
> infrastructure the flood can destroy.**

**So the phones are already a mesh. Nobody has turned them on.**

### And the counter-intuitive part, which is the whole idea

Every warning system in the world **degrades** as infrastructure fails. This one **improves** — because
the failure mode of infrastructure is exactly what makes the mesh work:

- **People cluster** when they flee, so phones come into range of each other
- **Phones stay on** when towers are down — a handset with no signal still has a battery and a radio
- **The payload is tiny** — a warning is a few dozen bytes; a Bluetooth advertisement is 31 and a frame
  here already fits in 20
- **The range is enough** — a village is not a city; 100 m per hop across a valley is a village-wide
  network with no equipment in it

**The system is strongest at the exact moment every other system is silent.** That is the inversion, and
nothing in the field is built on it.

## What makes it a global product rather than a national one

The mechanism is jurisdiction-free. What changes per country is one file:

| layer | global | local |
|---|---|---|
| transport | **Bluetooth mesh, phone to phone** | *nothing to change* |
| payload | a bounded frame with ttl and hops | *nothing to change* |
| reasoning | which way, how high, how long is left | **the elevation grid** |
| authority | who is legally obliged to act | **the routing table and the statute** |
| provenance | every claim names its source | *nothing to change* |

**Swap one data file and it runs in the Philippines, in Bangladesh, in Mozambique.** That is what makes
it a platform instead of a project — and it is why the Nepali version is a *deployment*, not the point.

## The three claims this could own, in order of how defensible they are

### 1. Warning delivery that is more reliable as infrastructure fails

The mesh. Measurable, demonstrable, and true of no existing system. **This is the headline.**

### 2. An AI that cannot state a fact without stating where it came from

Offline AI has a problem nobody has confronted: **with no server to check against, a model's output is
unverifiable.** The usual answer — *trust the model* — is unacceptable when the output is "run uphill
now".

This project already carries the answer as working machinery: **every number names its file, its
measurement and its caveat, and the caveats are enforced by tests.** Turned outward, that is not a
feature of one app. It is the missing precondition for AI that is allowed to act offline.

### 3. A warning that is actionable rather than a score

The field outputs risk. This outputs **which way, how high, and how many minutes are left** — computed
on the device, from data it already carries. *A risk score cannot be acted on by a person in the water.*

## What this is not

**Not another dashboard.** The field has enough.
**Not a model-accuracy claim.** Accuracy is not the bottleneck and never was.
**Not a national project.** Nepal is where it is built and proven, because that is where the data and the
mountain are. The claim is global.

## The sentence

> **Half the world gets no warning, and every system built to fix that dies with the network. The phones
> do not. Turn them into the network — a mesh that gets stronger as the infrastructure fails, carrying
> which way to run, how high, and how long is left, and able to say where every number came from.**
