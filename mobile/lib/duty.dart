// Who is responsible for the ground, on the phone, offline.
//
// Every complaint portal in Nepal routes to a municipality, and a municipality can say "not ours"
// and be finished with it. This carries the routing key's duty holder for each documented slope AND
// the local unit that office belongs to, with the unit's own gov.np site - so a letter can be
// addressed to something that exists.
//
// Two limits travel with the data and must not be dropped in the UI:
//   1. The office is the routing key's DEFAULT holder for a local road, not a per-parcel legal
//      determination. On a highway, in forest, or on private land the responsible body differs.
//   2. 119 of the 613 slopes name a unit the national gazetteer does not carry, and for those the
//      row has no district and no website. Saying so is better than inventing an address.
import 'dart:convert';
import 'dart:math' as math;

class Duty {
  final String id;
  final String title;
  final double lat;
  final double lon;
  final String office;

  /// The same duty in Nepali, from the one translation table in src/pahiro/complaints.py. Null when
  /// no translation is held - the letter falls back to the English there rather than inventing one.
  final String? officeNe;
  final String legal;
  final String? unit;
  final String? district;
  final String? site;

  const Duty({
    required this.id,
    required this.title,
    required this.lat,
    required this.lon,
    required this.office,
    required this.officeNe,
    required this.legal,
    required this.unit,
    required this.district,
    required this.site,
  });

  factory Duty.fromJson(Map<String, dynamic> j) => Duty(
        id: j['id'] as String,
        title: j['title'] as String,
        lat: (j['lat'] as num).toDouble(),
        lon: (j['lon'] as num).toDouble(),
        office: j['office'] as String,
        officeNe: j['officeNe'] as String?,
        legal: j['legal'] as String,
        unit: j['unit'] as String?,
        district: j['district'] as String?,
        site: j['site'] as String?,
      );

  bool get hasAddress => unit != null && unit!.isNotEmpty;

  /// What to put in a Nepali letter: the Nepali when it is held, otherwise the English.
  String officeFor(bool nepali) => (nepali && officeNe != null) ? officeNe! : office;
}

class DutyIndex {
  final List<Duty> slopes;
  final int resolved;
  const DutyIndex({required this.slopes, required this.resolved});

  static DutyIndex parse(String body) {
    final j = jsonDecode(body) as Map<String, dynamic>;
    return DutyIndex(
      slopes: (j['slopes'] as List)
          .map((x) => Duty.fromJson(x as Map<String, dynamic>))
          .toList(),
      resolved: ((j['counts'] as Map<String, dynamic>?)?['resolved'] as int?) ?? 0,
    );
  }

  /// The nearest documented slope, which is the only honest answer available: the record names
  /// slopes, not parcels.
  Duty? nearest(double lat, double lon) {
    Duty? best;
    var bd = double.infinity;
    for (final d in slopes) {
      final m = _haversine(lat, lon, d.lat, d.lon);
      if (m < bd) {
        bd = m;
        best = d;
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
