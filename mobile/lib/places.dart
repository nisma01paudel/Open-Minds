// Major places, on the phone, offline.
//
// These are the 277 local units this project could LOCATE - because the coordinates come from the
// mean position of the documented slopes whose titles name the unit, not from a surveyed town centre.
// 277 of Nepal's 753 units, because only the ones with mapped hazard records inside them have a
// position at all. That is stated here and must stay stated in the UI: a list of 277 that implies 753
// would be the same error as an empty trail list read as "nobody walks here".
//
// There is no prose in it. Name, Nepali name, district, population, area, official website, how many
// slopes are documented there and how densely OSM has mapped trails nearby - every field a machine
// checked, because prose about a place is the one thing nothing here can verify.
import 'dart:convert';
import 'dart:math' as math;

class GeoPlace {
  final String name;
  final String? nameNe;
  final String? district;
  final int? population;
  final String? site;
  final int slopes;
  final int trails;
  final double lat;
  final double lon;

  const GeoPlace({
    required this.name,
    required this.nameNe,
    required this.district,
    required this.population,
    required this.site,
    required this.slopes,
    required this.trails,
    required this.lat,
    required this.lon,
  });

  factory GeoPlace.fromFeature(Map<String, dynamic> f) {
    final p = f['properties'] as Map<String, dynamic>;
    final c = (f['geometry'] as Map<String, dynamic>)['coordinates'] as List;
    return GeoPlace(
      name: p['name'] as String,
      nameNe: p['name_ne'] as String?,
      district: p['district'] as String?,
      population: p['population'] as int?,
      site: p['website'] as String?,
      slopes: (p['slopes_documented'] as int?) ?? 0,
      trails: (p['trails_mapped_within_10km'] as int?) ?? 0,
      lon: (c[0] as num).toDouble(),
      lat: (c[1] as num).toDouble(),
    );
  }

  bool get hasWebsite => site != null && site!.isNotEmpty;
}

class PlaceList {
  final List<GeoPlace> all;
  const PlaceList({required this.all});

  static PlaceList parse(String body) {
    final j = jsonDecode(body) as Map<String, dynamic>;
    return PlaceList(
      all: (j['features'] as List)
          .map((f) => GeoPlace.fromFeature(f as Map<String, dynamic>))
          .toList(),
    );
  }

  /// Nearest places, with their distance. Distance is measured TO A LABEL POSITION, and the file's
  /// accuracy note says so - a large rural municipality is tens of kilometres across.
  List<(GeoPlace, double)> nearest(double lat, double lon, {int limit = 5}) {
    final scored = all
        .map((p) => (p, _haversine(lat, lon, p.lat, p.lon)))
        .toList()
      ..sort((a, b) => a.$2.compareTo(b.$2));
    return scored.take(limit).toList();
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
