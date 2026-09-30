"""What actually runs on the phone in someone's pocket, and what it costs them.

WHY THIS EXISTS
---------------
"AI on a mobile" is the easiest sentence in a pitch and the hardest to honour. Phones in the
districts this is built for are not flagship devices: they are 2-4 GB of RAM, often with the
storage nearly full, and the network is gone exactly when the app matters. A design that
assumes a 1.7 GB model on every handset has quietly excluded the people it claims to serve.

So this module is not a feature list. It is the honest ladder, built from the sizes measured in
docs/MODELS.md rather than from vendor claims, and the rule that makes it defensible:

    NOTHING THAT SAVES A LIFE IS BEHIND THE AI

Every capability that matters in the first hour - the SOS, the mesh, the Bluetooth-advertisement
beacon, the escape navigation, the statutory routing and the Nepali advisory text - is
deterministic and needs **zero megabytes of model**. `LIFESAVING` below is asserted to be inside
`TIER_NONE` by the tests, so the claim cannot quietly rot: if someone later moves the routing
behind an LLM, the suite fails.

The model tiers are therefore strictly additive quality. A phone that can afford 370 MB gets
image change detection and a real Nepali voice. A phone that can afford 1.5 GB also gets a
language model to write the advisory more fluently. A phone that can afford nothing still gets
the warning, the direction to run, and the mesh.

THE NUMBERS ARE MEASURED, NOT QUOTED
------------------------------------
From docs/MODELS.md, on a 6-core laptop CPU: DINOv2-S/14 int8 is 24.5 MB; the decision head is
under 5 MB; SmolVLM-256M Q8_0 is 279 MB; Qwen2.5-1.5B-Instruct Q4_K_M is 1117 MB; Piper
`ne_NP` chitwan medium is 63 MB and synthesises 9.5 s of Nepali speech in 1.3 s. Full stack is
about 1.7 GB on disk with a peak of roughly 3.0 GB resident.

Piper being 63 MB and MIT is the quiet win in that table, and it is worth saying out loud: the
Nepali voice does **not** need a hosted service, an API key or a token. It runs on the handset,
offline, in about a seventh of real time. A hosted text-to-speech call is precisely the
dependency that fails in the situation this app exists for.

RAM HEADROOM IS NOT THE MODEL SIZE
---------------------------------
A model does not only cost its file. Quantised inference needs working memory for the KV cache
and activations, and a phone has to keep its own operating system resident on top. `ram_for`
applies an explicit multiplier and floor rather than pretending the file size is the footprint,
because a recommendation that assumes 1.1 GB fits in 1.2 GB of free RAM is how an app gets
killed by the OS mid-evacuation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---- the measured components (docs/MODELS.md) ----------------------------------------------

DINOV2_MB = 24.5
DECISION_HEAD_MB = 5.0
SMOLVLM_MB = 279.0
QWEN_1_5B_MB = 1117.0
QWEN_0_5B_MB = 400.0        # smaller sibling of the pinned model, for the mid tier
PIPER_NE_MB = 63.0
TTS_RTF = 0.14              # measured: 1.3 s to synthesise 9.5 s of Nepali audio

# Inference needs working memory beyond the weights: KV cache, activations, and the OS the
# phone insists on keeping. Applied rather than assumed away.
WORKING_SET_MULTIPLIER = 1.8
OS_FLOOR_MB = 700.0


def ram_for(weights_mb: float) -> float:
    """Resident memory a phone must actually have free for a model of this size."""
    return weights_mb * WORKING_SET_MULTIPLIER + OS_FLOOR_MB


# ---- the ladder -----------------------------------------------------------------------------

# Features that must never depend on a model. The tests assert this set is inside TIER_NONE.
LIFESAVING = frozenset({
    "sos",                    # a distress call that composes and queues with no network
    "mesh_relay",             # store-and-forward between handsets
    "ble_beacon",             # the 20-byte advertisement a stranger's phone carries
    "escape_navigation",      # which way and how high, from the bundled DEM
    "statutory_routing",      # the ontology: who is legally responsible, cited
    "advisory_template",      # the Nepali advisory, assembled deterministically
    "offline_map",            # the bundled national view
})


@dataclass(frozen=True)
class Tier:
    name: str
    weights_mb: float
    components: tuple[str, ...]
    enables: frozenset[str]
    note: str

    @property
    def ram_mb(self) -> float:
        return ram_for(self.weights_mb)


TIER_NONE = Tier(
    name="none",
    weights_mb=0.0,
    components=(),
    enables=LIFESAVING,
    note="the warning, the direction, the mesh and the beacon - no model on the device at all",
)

TIER_VISION = Tier(
    name="vision",
    weights_mb=DINOV2_MB + DECISION_HEAD_MB + PIPER_NE_MB,
    components=("dino_v2_s14_int8", "decision_head", "piper_ne_np"),
    enables=LIFESAVING | {"change_detection", "nepali_voice"},
    note="sees change between two images and speaks Nepali on the handset, offline",
)

TIER_SEEING = Tier(
    name="seeing",
    weights_mb=DINOV2_MB + DECISION_HEAD_MB + SMOLVLM_MB + PIPER_NE_MB,
    components=("dino_v2_s14_int8", "decision_head", "smolvlm_256m_q8", "piper_ne_np"),
    enables=LIFESAVING | {"change_detection", "nepali_voice", "image_description"},
    note="describes what changed in words, rather than only scoring it",
)

TIER_FULL = Tier(
    name="full",
    weights_mb=DINOV2_MB + DECISION_HEAD_MB + SMOLVLM_MB + QWEN_1_5B_MB + PIPER_NE_MB,
    components=("dino_v2_s14_int8", "decision_head", "smolvlm_256m_q8",
                "qwen2_5_1_5b_q4_k_m", "piper_ne_np"),
    enables=LIFESAVING | {"change_detection", "nepali_voice", "image_description",
                          "written_advisory"},
    note="the pinned laptop stack; writes the advisory more fluently, and nothing more",
)

TIER_MID = Tier(
    name="mid",
    weights_mb=DINOV2_MB + DECISION_HEAD_MB + QWEN_0_5B_MB + PIPER_NE_MB,
    components=("dino_v2_s14_int8", "decision_head", "qwen2_5_0_5b_q4_k_m", "piper_ne_np"),
    enables=LIFESAVING | {"change_detection", "nepali_voice", "written_advisory_small"},
    note="a smaller language model where 1.5B will not fit, for a plainer advisory",
)

# Largest first, so `fit` can take the first one that is affordable. The order is asserted by
# the tests to match the weights: an out-of-order ladder silently hands a phone a tier that is
# not the best it can run.
LADDER: tuple[Tier, ...] = (TIER_FULL, TIER_MID, TIER_SEEING, TIER_VISION, TIER_NONE)


@dataclass
class Device:
    """What the handset reports, or what we assume when it reports nothing."""

    ram_mb: float
    storage_free_mb: float
    source: str = "reported"

    @classmethod
    def unknown(cls) -> "Device":
        """The conservative default for a device we cannot measure.

        Not an error and not a failure: it is the phone most likely to be in the valley, and
        the floor still works on it.
        """
        return cls(ram_mb=1500.0, storage_free_mb=200.0, source="assumed (2 GB handset)")


@dataclass
class Fit:
    tier: Tier
    device: Device
    reason: str
    limits: list[str] = field(default_factory=list)

    @property
    def missing(self) -> frozenset[str]:
        return TIER_FULL.enables - self.tier.enables

    def explain(self) -> str:
        lines = [f"{self.tier.name}: {self.tier.note}",
                 f"  needs about {self.tier.ram_mb:.0f} MB resident, "
                 f"{self.tier.weights_mb:.0f} MB on disk",
                 f"  decided from {self.device.source}: {self.reason}"]
        if self.missing:
            lines.append(f"  will not do: {', '.join(sorted(self.missing))}")
        lines.extend(f"  limit: {x}" for x in self.limits)
        return "\n".join(lines)


def fit(device: Device | None = None, *, want: str | None = None) -> Fit:
    """Choose the largest tier this device can actually run.

    `want` pins a tier by name, and is refused rather than honoured when the device cannot run
    it - a silently downgraded model is a bug report waiting to happen.
    """
    device = device or Device.unknown()
    limits: list[str] = []

    if device.storage_free_mb < TIER_VISION.weights_mb:
        # Even the vision tier will not fit on disk. Say so plainly; the floor still works.
        return Fit(TIER_NONE, device,
                   f"only {device.storage_free_mb:.0f} MB of storage free, "
                   f"short of the {TIER_VISION.weights_mb:.0f} MB smallest model set",
                   limits=["no on-device model fits; the deterministic path is in use"])

    candidates = LADDER
    if want is not None:
        chosen = next((t for t in LADDER if t.name == want), None)
        if chosen is None:
            raise ValueError(f"unknown tier {want!r}; expected one of "
                             f"{[t.name for t in LADDER]}")
        if chosen.ram_mb > device.ram_mb or chosen.weights_mb > device.storage_free_mb:
            limits.append(f"'{want}' was requested but does not fit; using what does")
        else:
            return Fit(chosen, device, "requested and affordable", limits)

    for tier in candidates:
        if tier.ram_mb <= device.ram_mb and tier.weights_mb <= device.storage_free_mb:
            reason = (f"{tier.ram_mb:.0f} MB resident fits in {device.ram_mb:.0f} MB, "
                      f"{tier.weights_mb:.0f} MB on disk fits in "
                      f"{device.storage_free_mb:.0f} MB")
            return Fit(tier, device, reason, limits)

    return Fit(TIER_NONE, device, "no model tier fits this device", limits)


def tier_by_name(name: str) -> Tier:
    for t in LADDER:
        if t.name == name:
            return t
    raise ValueError(f"unknown tier {name!r}")


def ladder_summary() -> list[dict]:
    """The ladder as data, for a docs table or a settings screen."""
    return [{
        "name": t.name,
        "weights_mb": round(t.weights_mb, 1),
        "ram_mb": round(t.ram_mb, 0),
        "components": list(t.components),
        "enables": sorted(t.enables),
        "note": t.note,
    } for t in sorted(LADDER, key=lambda x: x.weights_mb)]
