// When to go — the twelve-month guide, on the phone, offline.
//
// This is the question a person actually asks before taking a week off, and it is the one thing
// every trekking site answers with marketing. The file behind it reports rain, dry days and
// temperature and labels no month good or bad, because a farmer, a trekker and a paraglider want
// different weather from the same month.
//
// Two things the data itself insists on and this code must not hide:
//   1. Only June to September were cross-checked against this project's own CHIRPS measurement.
//      The other eight months are model output alone and are marked validated: false.
//   2. Kathmandu failed that cross-check - ERA5 puts nearly twice the measured monsoon there - so
//      the region carries a verdict saying its rain figures should not be quoted.
//
// A phone that showed twelve confident bars and a happy summary would be repeating exactly the kind
// of claim this project exists to refuse.
import 'dart:convert';
import 'dart:math' as math;

class SeasonMonth {
  final int month;
  final String name;
  final double rainMmPerDay;
  final double dryDayPct;
  final double? tMaxC;
  final double? tMinC;
  final bool validated;

  const SeasonMonth({
    required this.month,
    required this.name,
    required this.rainMmPerDay,
    required this.dryDayPct,
    required this.tMaxC,
    required this.tMinC,
    required this.validated,
  });

  factory SeasonMonth.fromJson(Map<String, dynamic> j) => SeasonMonth(
        month: j['month'] as int,
        name: j['name'] as String,
        rainMmPerDay: (j['rain_mm_per_day'] as num?)?.toDouble() ?? 0,
        dryDayPct: (j['dry_day_pct'] as num?)?.toDouble() ?? 0,
        tMaxC: (j['t_max_c'] as num?)?.toDouble(),
        tMinC: (j['t_min_c'] as num?)?.toDouble(),
        validated: j['validated'] == true,
      );
}

class SeasonRegion {
  final String key;
  final String name;
  final double lat;
  final double lon;
  final List<SeasonMonth> months;
  final bool reliable;
  final String verdict;

  const SeasonRegion({
    required this.key,
    required this.name,
    required this.lat,
    required this.lon,
    required this.months,
    required this.reliable,
    required this.verdict,
  });

  SeasonMonth get driest =>
      months.reduce((a, b) => a.rainMmPerDay <= b.rainMmPerDay ? a : b);
  SeasonMonth get wettest =>
      months.reduce((a, b) => a.rainMmPerDay >= b.rainMmPerDay ? a : b);
}

class SeasonGuide {
  final List<SeasonRegion> regions;
  final String note;

  const SeasonGuide({required this.regions, required this.note});

  static SeasonGuide parse(String body) {
    final j = jsonDecode(body) as Map<String, dynamic>;
    final regions = (j['regions'] as List).map((r) {
      final m = r as Map<String, dynamic>;
      final v = (m['validation'] as Map<String, dynamic>?) ?? const {};
      return SeasonRegion(
        key: m['key'] as String,
        name: m['name'] as String,
        lat: (m['lat'] as num).toDouble(),
        lon: (m['lon'] as num).toDouble(),
        months: (m['months'] as List)
            .map((x) => SeasonMonth.fromJson(x as Map<String, dynamic>))
            .toList(),
        reliable: v['reliable'] == true,
        verdict: (v['verdict'] as String?) ?? '',
      );
    }).toList();
    return SeasonGuide(
      regions: regions,
      note: (j['read_this_as'] as String?) ?? '',
    );
  }

  /// The region whose centre is nearest, by great-circle distance.
  SeasonRegion? nearest(double lat, double lon) {
    if (regions.isEmpty) return null;
    SeasonRegion best = regions.first;
    var bd = double.infinity;
    for (final r in regions) {
      final d = _haversine(lat, lon, r.lat, r.lon);
      if (d < bd) {
        bd = d;
        best = r;
      }
    }
    return best;
  }
}

double _haversine(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371000.0;
  final p1 = lat1 * math.pi / 180, p2 = lat2 * math.pi / 180;
  final dp = (lat2 - lat1) * math.pi / 180, dl = (lon2 - lon1) * math.pi / 180;
  final a = math.sin(dp / 2) * math.sin(dp / 2) +
      math.cos(p1) * math.cos(p2) * math.sin(dl / 2) * math.sin(dl / 2);
  return r * 2 * math.asin(math.sqrt(a.clamp(0.0, 1.0)));
}
