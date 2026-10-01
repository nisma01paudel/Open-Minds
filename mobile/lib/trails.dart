/// Hiking trails on the handset, with no network at all.
///
/// The trail bundle is the SAME file the web app serves - copied, not regenerated - so the two
/// halves of the project cannot disagree about where a path goes. It is vector geometry: small,
/// correct at every zoom, and it works with the radio off.
///
/// WHAT THIS DOES AND DOES NOT DO
///
/// It answers the question a walker standing on a hillside actually asks: what can I walk from
/// here. It does NOT do point-to-point routing over the network - the Python side does that, and
/// duplicating a graph router in a second language is how two implementations quietly start
/// disagreeing. The list below is the feature that matters and the one that survives the fact
/// that Nepali footpath data is fragmented.
///
/// Trail data (c) OpenStreetMap contributors, ODbL 1.0. The attribution travels in the bundle and
/// must be shown wherever the data is.
library;

import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

const double earthRadiusM = 6371008.8;

/// Below this a stretch of pavement is not a walk. Matches the Python side.
const double minTrailM = 150.0;

double haversineM(double lon1, double lat1, double lon2, double lat2) {
  final p1 = lat1 * math.pi / 180.0, p2 = lat2 * math.pi / 180.0;
  final dp = p2 - p1;
  final dl = (lon2 - lon1) * math.pi / 180.0;
  final h = math.sin(dp / 2) * math.sin(dp / 2) +
      math.cos(p1) * math.cos(p2) * math.sin(dl / 2) * math.sin(dl / 2);
  return 2 * earthRadiusM * math.asin(math.min(1.0, math.sqrt(h)));
}

class Trail {
  final String name;

  /// The OSM `highway` tag: path, track, footway, steps, bridleway.
  ///
  /// This is the field the parser should always have read. It was reading `n` and `d`, neither of
  /// which exists anywhere in the shipped file - so `name` was empty for all 23,726 trails and the
  /// screen printed "(unnamed path)" beside "not recorded" for every one of them, twice over, while
  /// the actual type sat unread in `h`.
  final String highway;
  final double lengthM;
  final double nearestM;
  final List<List<double>> points;

  const Trail({
    required this.name,
    required this.highway,
    required this.lengthM,
    required this.nearestM,
    required this.points,
  });

  /// Naismith's rule, the same one the Python side uses: 5 km/h flat, a minute per 10 m climbed.
  /// Climbing is not available here - the terrain grid is a kilometre a cell - so this is the
  /// distance-only figure and is labelled as such in the UI.
  int get flatMinutes => (lengthM / 1000.0 / 5.0 * 60.0).round();

  /// A real name if OSM has one, otherwise empty - the type label belongs to the UI, which owns
  /// the language, and every one of these trails is unnamed anyway.
  String get label => name;
}

class TrailNetwork {
  final List<Trail> trails;
  final String attribution;
  final String region;

  const TrailNetwork({
    required this.trails,
    required this.attribution,
    required this.region,
  });

  /// Parse the bundled FeatureCollection. Each feature IS one trail - the OSM way - so a trail
  /// needs no grouping here, unlike the Python graph which has to reassemble ways from edges.
  static TrailNetwork parse(String source) {
    final data = json.decode(source) as Map<String, dynamic>;
    final features = (data['features'] as List?) ?? const [];
    final trails = <Trail>[];

    for (final f in features) {
      final geom = (f as Map)['geometry'] as Map?;
      if (geom == null || geom['type'] != 'LineString') continue;
      final raw = (geom['coordinates'] as List?) ?? const [];
      final pts = <List<double>>[];
      for (final c in raw) {
        final pair = c as List;
        pts.add([(pair[0] as num).toDouble(), (pair[1] as num).toDouble()]);
      }
      if (pts.length < 2) continue;
      final props = (f['properties'] as Map?) ?? const {};
      double length = 0;
      for (var i = 1; i < pts.length; i++) {
        length += haversineM(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]);
      }
      trails.add(Trail(
        name: (props['n'] as String?) ?? '',
        highway: (props['h'] as String?) ?? '',
        lengthM: length,
        nearestM: 0,
        points: pts,
      ));
    }
    return TrailNetwork(
      trails: trails,
      attribution: (data['attribution'] as String?) ?? '',
      // `region` (singular) was replaced by `regions` (plural) when the bundle went
      // multi-region. Reading the old key returned '' forever and nothing noticed,
      // because the field is parsed and never displayed.
      region: (data['region'] as String?)
          ?? ((data['regions'] as List?)?.length != null
              ? '${(data['regions'] as List).length} regions' : ''),
    );
  }

  static TrailNetwork fromBytes(Uint8List bytes) =>
      parse(utf8.decode(bytes));

  /// Trails whose mapped line passes within [radiusM] of a point, longest first.
  ///
  /// Longest first because a person who has walked to a trailhead wants the walk, not the 200 m
  /// spur at the car park.
  List<Trail> nearby(double lon, double lat,
      {double radiusM = 3000.0, int limit = 8}) {
    final out = <Trail>[];
    for (final t in trails) {
      var best = double.infinity;
      for (final p in t.points) {
        final d = haversineM(lon, lat, p[0], p[1]);
        if (d < best) best = d;
        if (best <= radiusM && best < 50) break; // close enough; stop scanning
      }
      if (best > radiusM) continue;
      if (t.lengthM < minTrailM) continue;   // a spur is not a walk; Python filters here too
      out.add(Trail(
        name: t.name,
        highway: t.highway,
        lengthM: t.lengthM,
        nearestM: best,
        points: t.points,
      ));
    }
    out.sort((a, b) => b.lengthM.compareTo(a.lengthM));
    return out.length > limit ? out.sublist(0, limit) : out;
  }
}
