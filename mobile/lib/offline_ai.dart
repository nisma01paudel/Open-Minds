/// What actually runs on the phone in someone's pocket, and the rule that governs it.
///
/// The Dart port of `src/pahiro/offline_ai.py`. The rule is the important part:
///
///     NOTHING THAT SAVES A LIFE IS BEHIND THE AI
///
/// Every capability that matters in the first hour - the SOS, the mesh, the beacon, the escape
/// direction, the routing and the advisory - is deterministic and needs **zero megabytes of
/// model**. [lifesaving] is asserted by the tests to be inside [tierNone], so the claim cannot
/// quietly rot: if someone later moves routing behind a language model, the suite fails.
///
/// Sizes are the measured ones from docs/MODELS.md, not vendor claims.
library;

const double dinov2Mb = 24.5;
const double decisionHeadMb = 5.0;
const double smolvlmMb = 279.0;
const double qwen15bMb = 1117.0;
const double qwen05bMb = 400.0;
const double piperNeMb = 63.0;

/// Measured: 1.3 s to synthesise 9.5 s of Nepali audio, on a CPU, with no network.
const double ttsRtf = 0.14;

/// Inference needs working memory beyond the weights - KV cache, activations - and the phone
/// insists on keeping its own operating system resident. Applied rather than assumed away: a
/// recommendation that assumes 1.1 GB fits in 1.2 GB of free RAM is how an app gets killed by
/// the OS mid-evacuation.
const double workingSetMultiplier = 1.8;
const double osFloorMb = 700.0;

double ramFor(double weightsMb) => weightsMb * workingSetMultiplier + osFloorMb;

/// Features that must never depend on a model.
const Set<String> lifesaving = {
  'sos',
  'mesh_relay',
  'ble_beacon',
  'escape_navigation',
  'statutory_routing',
  'advisory_template',
  'offline_map',
};

class Tier {
  final String name;
  final double weightsMb;
  final List<String> components;
  final Set<String> enables;
  final String note;

  const Tier({
    required this.name,
    required this.weightsMb,
    required this.components,
    required this.enables,
    required this.note,
  });

  double get ramMb => ramFor(weightsMb);
}

const Tier tierNone = Tier(
  name: 'none',
  weightsMb: 0.0,
  components: [],
  enables: lifesaving,
  note: 'the warning, the direction, the mesh and the beacon - no model on the device at all',
);

const Tier tierVision = Tier(
  name: 'vision',
  weightsMb: dinov2Mb + decisionHeadMb + piperNeMb,
  components: ['dino_v2_s14_int8', 'decision_head', 'piper_ne_np'],
  enables: {...lifesaving, 'change_detection', 'nepali_voice'},
  note: 'sees change between two images and speaks Nepali on the handset, offline',
);

const Tier tierSeeing = Tier(
  name: 'seeing',
  weightsMb: dinov2Mb + decisionHeadMb + smolvlmMb + piperNeMb,
  components: ['dino_v2_s14_int8', 'decision_head', 'smolvlm_256m_q8', 'piper_ne_np'],
  enables: {...lifesaving, 'change_detection', 'nepali_voice', 'image_description'},
  note: 'describes what changed in words, rather than only scoring it',
);

const Tier tierMid = Tier(
  name: 'mid',
  weightsMb: dinov2Mb + decisionHeadMb + qwen05bMb + piperNeMb,
  components: ['dino_v2_s14_int8', 'decision_head', 'qwen2_5_0_5b_q4_k_m', 'piper_ne_np'],
  enables: {...lifesaving, 'change_detection', 'nepali_voice', 'written_advisory_small'},
  note: 'a smaller language model where 1.5B will not fit, for a plainer advisory',
);

const Tier tierFull = Tier(
  name: 'full',
  weightsMb: dinov2Mb + decisionHeadMb + smolvlmMb + qwen15bMb + piperNeMb,
  components: [
    'dino_v2_s14_int8',
    'decision_head',
    'smolvlm_256m_q8',
    'qwen2_5_1_5b_q4_k_m',
    'piper_ne_np',
  ],
  enables: {
    ...lifesaving,
    'change_detection',
    'nepali_voice',
    'image_description',
    'written_advisory',
  },
  note: 'the pinned laptop stack; writes the advisory more fluently, and nothing more',
);

/// Largest first, so [fit] takes the first tier that is affordable. Asserted against the weights
/// by the tests: an out-of-order ladder silently hands a phone a tier it did not have to settle
/// for.
const List<Tier> ladder = [tierFull, tierMid, tierSeeing, tierVision, tierNone];

class Device {
  final double ramMb;
  final double storageFreeMb;
  final String source;

  const Device({
    required this.ramMb,
    required this.storageFreeMb,
    this.source = 'reported',
  });

  /// The conservative default for a device we cannot measure. Not an error: it is the phone most
  /// likely to be in the valley, and the floor still works on it.
  static const Device unknown = Device(
    ramMb: 1500.0,
    storageFreeMb: 200.0,
    source: 'assumed (2 GB handset)',
  );
}

class Fit {
  final Tier tier;
  final Device device;
  final String reason;
  final List<String> limits;

  const Fit(this.tier, this.device, this.reason, [this.limits = const []]);

  Set<String> get missing => tierFull.enables.difference(tier.enables);
}

/// Choose the largest tier this device can actually run.
Fit fit([Device? device]) {
  final d = device ?? Device.unknown;
  final limits = <String>[];

  if (d.storageFreeMb < tierVision.weightsMb) {
    return Fit(
      tierNone,
      d,
      'only ${d.storageFreeMb.toStringAsFixed(0)} MB of storage free, short of the '
          '${tierVision.weightsMb.toStringAsFixed(0)} MB smallest model set',
      ['no on-device model fits; the deterministic path is in use'],
    );
  }

  for (final tier in ladder) {
    if (tier.ramMb <= d.ramMb && tier.weightsMb <= d.storageFreeMb) {
      return Fit(
        tier,
        d,
        '${tier.ramMb.toStringAsFixed(0)} MB resident fits in ${d.ramMb.toStringAsFixed(0)} MB, '
            '${tier.weightsMb.toStringAsFixed(0)} MB on disk fits in '
            '${d.storageFreeMb.toStringAsFixed(0)} MB',
        limits,
      );
    }
  }
  return Fit(tierNone, d, 'no model tier fits this device', limits);
}
