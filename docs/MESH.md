# The mesh, the API, and finding someone under the debris

This document covers the second half of Pahiro. The first half warns that a slope is
loaded and names the office on the hook for it. This half is what happens after it fails:
the road is gone, the tower is gone, and there are people under the slide.

Three pieces, and they exist because of one fact — **a landslide takes the network with
it.** Every tool that assumes a connection is useless at exactly the moment it is needed.

```
   villager's phone ──Bluetooth──> passer-by ──Bluetooth──> bazaar ──2G──> THE API
        (SOS, no signal)          (no signal either)     (one bar)      (the board)

   rescuer's phone ──RSSI sightings──> THE API ──> "search a 15 m circle here"
```

---

## 1. Bluetooth mesh chat — `src/pahiro/mesh/`

Messages travel phone to phone, carried by whoever happens to walk within range. The
protocol is small on purpose.

### Four rules the format obeys

| Rule | Why |
|---|---|
| **Small** | The radio is low-bandwidth and the phone is on battery. |
| **Self-contained** | A relay cannot look anything up. It may never have had a network. |
| **Idempotent** | A flood means duplicates. A node must detect one from the message alone. |
| **Degradable** | A phone at 3% battery and a bad fix can still emit something useful. |

JSON, not packed bytes. That costs roughly 2–3× the bytes and buys the ability to read a
message off a serial log, or type one by hand into a terminal, *during an actual rescue*.
Correctness under pressure beats bytes. `MeshMessage.to_bytes/from_bytes` is the only place
that changes if that trade is ever revisited.

### TTL and the flood

Every message carries a time-to-live that decrements per hop, and a hop count that
increments. TTL is what stops a flood becoming a broadcast storm on a radio shared with the
people you are trying to save. **Seven hops** covers a valley, not a country.

### The three behaviours that make it a mesh

- **Dedupe.** Store the id on first sight, ignore every later copy. Without it the mesh
  amplifies itself instead of carrying anything.
- **Store and forward.** A relayed message is *not* deleted. It is held, so it can be handed
  to the next phone that appears — including one that arrives hours later. This is the whole
  difference between a mesh and a walkie-talkie: **the listener need not be there when the
  message was sent.**
- **Priority eviction.** Storage is bounded because a phone is not a server. When it is full,
  chat goes first and a distress message is the last thing dropped. A node would rather hold
  200 SOS messages than 200 pleasantries.

### The radios

| Class | Purpose |
|---|---|
| `LoopbackRadio` | In-memory medium. Every attached node hears every broadcast. |
| `LossyRadio` | Configurable drop rate and range. Answers "does it survive half the frames being lost?" |
| `BleTransport` | The interface a real device implements. **Declared, not faked.** |

**There is no pretend Bluetooth stack in this repository.** `BleTransport`'s methods raise
`NotImplementedError` with a note on what a real implementation needs — Web Bluetooth
(central role, foreground only) on Android, or a native shim where background advertising is
required, which a browser cannot provide. Splitting the logic from the radio is what makes
the logic testable at all; a protocol that can only be tested on two phones in a field is
wrong in ways nobody finds until the field.

---

## 2. The field API — `src/pahiro/api.py`

An API, not another screen. A warning is information; what is missing in the hours after a
slope fails is **a common place for the things that are happening to land**, so that a phone
in a village, a phone carried by a rescuer, and a desk in the district office are all looking
at the same picture.

```
GET  /api/v1/health                  liveness + counters
GET  /api/v1/openapi.json            machine-readable schema
POST /api/v1/mesh/messages           messages that reached the internet over someone's phone
GET  /api/v1/mesh/messages?since=    sync the delta, not the world
POST /api/v1/sos                     a distress report, with or without a position
GET  /api/v1/trapped                 everyone who has called for help, worst first
POST /api/v1/track/{device_id}       one rescuer's RSSI sighting of a buried handset
GET  /api/v1/track/{device_id}       estimated position and search radius
GET  /api/v1/slopes                  the warning data, so one client needs one backend
```

```bash
python -m pahiro.api --port 8080 --data evidence/field.json
```

### Designed for a bad network

- **Every write is idempotent.** A phone that has no idea whether its last frame got through
  will send it again. The device supplies its own frame id — exactly as it does on the mesh —
  and reuses it on the retry. A server-generated id cannot give idempotency, because the
  retry looks like a brand-new message. (This was a real bug: the first version generated the
  id server-side, and a retried SOS grew a phantom victim.)
- **Reads take `?since=`.** A device offline for six hours syncs the delta.
- **No sessions.** A session is a thing that expires while you are under a rock.
- **One row per handset on the board.** A frightened person sends four messages; a board that
  lists all four buries everyone else.
- **`X-Device-Id` or a body field.** No accounts.

---

## 3. Finding a trapped phone — `src/pahiro/locate.py`

A person under a landslide is under rock, wet soil and metal. Their phone has no GPS fix —
the sky is not visible — and no network. What it has is a battery and a radio. If it keeps
advertising, a rescuer walking the debris can hear it, and the signal gets stronger as they
get closer.

### The model

```
RSSI = TX_POWER − 10 · n · log₁₀(d)
```

`n` ≈ 2.0 in free air. Under debris `n` is higher, so signal falls off faster, so an assumed
`n` **under-estimates** the distance. That error direction matters and is stated rather than
buried: an under-estimate means the search area still contains the person.

### Why the output is a radius, not a point

Three receivers with noisy RSSI give a position *and a residual*, and the residual is large
because the medium is not uniform — a boulder between the phone and one rescuer can cost
20 dB. A confident-looking coordinate would send a team to dig in one spot. A circle sends
them to search an area. `PositionEstimate` always carries `radius_m`, `confidence` and
`search_area_m2`.

### What it refuses to do

| Receivers | Behaviour |
|---|---|
| 1 | A distance and a circle. Says "move and read again to get a direction". |
| 2 | **Refuses to triangulate.** Two circles cross in two places; geometry cannot choose. Returns a bearing and says so. |
| ≥3, collinear | Says the receivers are in a line and carry no perpendicular information. Does not return a number produced by a singular matrix. |
| ≥3 | Weighted least squares, weights `1/d²` — a reading at 5 m says more than one at 200 m. |

### Measured, not asserted

With a target placed by hand and RSSI generated from the same model, the estimator recovers
it to **under 25 m** (`tests/test_locate.py`). The end-to-end demo lands **20 m** from the
true position with a 15 m search radius and a 3 m residual.

That does not prove the model matches real debris — nothing here can. It proves the
arithmetic and the geometry are right, which is the part that must be right before the model
is worth arguing about.

---

## 4. Run it

```bash
# the whole story, one command, no network needed at any point
python scripts/demo_mesh_rescue.py

# the API
python -m pahiro.api --port 8080
curl -s -X POST localhost:8080/api/v1/sos -H 'Content-Type: application/json' \
     -d '{"device_id":"phone-1","message":"buried near the culvert","lat":27.762,"lon":85.0575,"people":2,"id":"f1"}'
```

---

## What this is honest about

- **Bluetooth does not go through rock.** The mesh carries *messages*, not voices. It works
  because people move — that is what makes the hops.
- **A distance inferred from a signal that crossed six metres of debris is not a distance.**
  Hence the radius.
- **The radio is declared, not implemented.** No pretend Bluetooth stack ships here.
- **Nobody has tested this on a real phone in a real valley.** The tests prove the protocol,
  the geometry and the API. They do not prove the radio.
