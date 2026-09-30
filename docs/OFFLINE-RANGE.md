# How far can software actually reach?

The question was: *research how the software can reach in kilometres.* This is the honest answer,
including the part where the answer is "it cannot, and here is what it can do instead".

## The short version

**No software trick increases a radio's range.** Range is set by transmit power, antenna and the
regulations governing them — all of which belong to the handset, not to us. Anyone claiming a
software change turns a phone into a kilometre-scale transmitter is either using a radio we do not
have, or mistaken.

What software *can* do, and what this project does, is three things:

1. **Multiply hops.** Reach is `hops × hop_range` when there are phones to relay through. This is
   the only way a phone-only system covers ground.
2. **Drive a radio that does reach kilometres** — LoRa or VHF packet. That needs hardware, and the
   brief excludes it, so it is named here rather than smuggled in.
3. **Never lose the message in between** — hold, offer, acknowledge, expire. This is where the
   real engineering is, and it is what `src/pahiro/mesh/dtn.py` implements.

## Measured ranges, with sources

| Link | Realistic range | Source |
|---|---|---|
| Bluetooth LE advertisement | ~30 m | Spec-class range at legal TX power; the beacon design assumes tens of metres, never more |
| Smartphone Wi-Fi (measured, not claimed) | **~300 m** | [Smartphones in wireless communication without mobile networks](https://www.duo.uio.no/bitstream/handle/10852/53773/Smartphones-in-wireless-communication-without-mobile-networks.pdf) — a real measurement of consumer handsets |
| Wi-Fi Aware / Direct, phone-to-phone | 100–300 m | Uses the same chip and budget; line-of-sight helps, terrain does not |
| SMS | Whole cell network | Independent of distance; needs a tower standing and a sender willing to pay |
| LoRa (SX127x class) | **2–15 km** | Needs a radio module — **hardware, excluded** |
| VHF packet over a handheld | 5–30 km | Needs a handheld — but see Codec2 below, which is the interesting case |
| A person walking | Unlimited | The floor of the ladder, and the only rung that never fails |

`dtn.py` carries the 300 m figure for the Wi-Fi rung, taken from that measurement rather than from
a vendor's optimistic number.

## What already exists on GitHub, and what it is good for

The research question was really "is someone else solving this". Several people are, and the
honest thing is to name them and say which gap this project fills.

- **[Reticulum](https://github.com/HonestLocksmith/Reticulum)** — *"the cryptography-based
  networking stack for building unstoppable networks with LoRa, Packet Radio, WiFi and everything
  in between."* This is the reference design for long-range, infrastructure-free networking, and
  it is the closest thing to what the transport ladder is reaching for. It is a general-purpose
  stack; this project is a disaster-specific application on top of the same idea, and
  `docs/PRIOR-ART.md` should credit it as such.
- **[Serval Mesh](https://www.elektormagazine.com/articles/serval-mesh-operating-mobile-phones-without-a-cellular-network)**
  — operating phones without a cellular network, over Wi-Fi mesh. The proof that phone-to-phone
  meshing works in the field, and the source of the hard-won lesson that battery and user
  behaviour, not radio, are the limiting factors.
- **[Meshtastic](https://wiki.heltec.org/news/building-a-lifeline-in-the-storm/building-a-life-line-in-the-storm)**
  — LoRa mesh, actively used in disaster response (see [this Philippines deployment](https://www.seeedstudio.com/blog/2025/07/03/empowering-disaster-resilience-in-the-philippines-with-sensecap-t1000-e-meshtastic-solutions/)).
  It reaches kilometres per hop. It requires a LoRa board, so it is out of scope by the brief — but
  it is the thing to point at when a judge asks "what about real long range".
- **[Codec2 / FreeDV](https://sourceforge.net/p/freetel/mailman/freetel-codec2/thread/CAMeUeEDkaRYXBqvx%2B7-Gwpbv8AgLJ%3DEfSEQ56Dh6ajDuh3RWcw%40mail.gmail.com/)**
  — the genuinely clever one. Codec2 and FreeDV move **data over a voice-grade radio channel**, so a
  cheap VHF handheld that people already own becomes a packet link reaching tens of kilometres. The
  software is open, and it is the only route to kilometres that runs on hardware a Nepali ward
  might already have.

## What that means for this project's claim

The ladder in `dtn.py` is the right shape and it is honest about its ceiling:

    ble         30 m   →  wifi_aware  300 m   →  sms  any cell   →  courier  unlimited

Two rungs reach further than a phone can on its own: **SMS**, because it borrows a tower, and
**the courier**, because it borrows a person. Neither is a radio trick. That is the entire honest
answer to "how far can software reach": **as far as the hops, the towers and the people go, and no
further.**

The contribution is not the reach. It is that **the message is never dropped for want of a
transport** — it is held — and that the same call arriving twice is counted once. Any of the
projects above can carry a frame. This one refuses to lose it.

## What I would add next, in order

1. **A Reticulum-compatible interface.** Rather than reimplementing a general stack, expose the
   bundle store as a Reticulum `Interface` so this rides their routing when they are present and
   ours when they are not. That is the largest reach increase available in software alone.
2. **Codec2 as a transport.** If a ward has a VHF handheld, `dtn.py` already has the seam for it —
   a transport with a large `range_m` and a low `max_payload`. Adding Codec2 turns tens of
   kilometres into a supported rung without asking anyone to buy a LoRa board.
3. **SMS as a real transport, not a modelled one.** The rung exists in the ladder; wiring an actual
   SMS gateway is what makes it real, and it is the cheapest kilometre-scale win.

## The caveat that goes on all of it

None of this has been tested on real handsets in a real valley. The ranges above are measured by
other people, on other devices, in other terrain. The custody rules are tested; the radios are not.
