/// Where to run, and how high - on the handset, with no server and no network.
///
/// This is the Dart port of `src/pahiro/shelter.py` and `src/pahiro/navigate.py`, and it exists
/// for one reason: the phone in the valley cannot reach an API. A warning that needs a network
/// to tell you which way to run has failed at exactly the moment it was needed.
///
/// The elevation grid ships as an asset (852 KB, all of Nepal at roughly a kilometre a cell), so
/// the answer is computed on the device. The wire reasoning is unchanged from the Python:
///
///   - the direction comes from the **local fall line**, not from the nearest higher grid cell,
///     because on a coarse grid the nearest higher cell is routinely one pixel away in an
///     arbitrary direction. At Melamchi that said "south" - which in a valley is as likely to be
///     downstream as up the hillside, and running downstream is how people die;
///   - candidates more than 75 degrees off the fall line are rejected;
///   - **refusing is a valid answer**: in the Terai there is no nearby high ground and the honest
///     instruction is not to run for it;
///   - every answer carries its own limitation, because a DEM cannot see bridges, culverts,
///     roads or the water.
library;

import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

/// A flash flood in a Nepali gully typically rises 3-6 m above the channel bed in minutes.
const double defaultRiseM = 5.0;

/// Pessimistic on-foot reach: 2 km is about half an hour flat, and longer uphill in the dark.
const double maxWalkM = 2000.0;

/// Climbing one metre costs roughly what walking eight metres on the flat costs. This is what
/// stops the planner sending someone up a 300 m cliff face because it was marginally closer.
const double climbPenalty = 8.0;

/// A target must clear the expected rise by this much as well, so that "safe" ground is not the
/// bank of the same stream one cell over.
const double safetyMarginM = 2.0;

const List<String> compass = [
  'north', 'north-east', 'east', 'south-east',
  'south', 'south-west', 'west', 'north-west',
];

/// The same eight directions in Nepali. A sentence that mixes "पानी आउनुअघि east तर्फ" is worse
/// than no Nepali at all: the reader has to translate the one word the instruction turns on, in
/// the seconds they do not have.
const List<String> compassNe = [
  'उत्तर', 'उत्तर-पूर्व', 'पूर्व', 'दक्षिण-पूर्व',
  'दक्षिण', 'दक्षिण-पश्चिम', 'पश्चिम', 'उत्तर-पश्चिम',
];

int compassIndex(double bearingDeg) => ((bearingDeg + 22.5) % 360 ~/ 45);

/// A local elevation grid, ready to sample. Fully offline.
class Dem {
  final Uint16List elevation;
  final int rows;
  final int cols;
  final double west;
  final double south;
  final double east;
  final double north;

  Dem({
    required this.elevation,
    required this.rows,
    required this.cols,
    required this.west,
    required this.south,
    required this.east,
    required this.north,
  });

  /// Read the bundled national DEM. Returns null if the asset is absent, which the UI reports
  /// rather than crashing - the rest of the app does not depend on terrain.
  static Dem? fromBytes(Uint8List binBytes, String metaJson) {
    final meta = jsonDecode(metaJson) as Map<String, dynamic>;
    final width = meta['width'] as int;
    final height = meta['height'] as int;
    if (binBytes.length < width * height * 2) return null;

    // Little-endian uint16, as written by the terrain builder.
    final buffer = binBytes.buffer.asUint16List(
      binBytes.offsetInBytes,
      width * height,
    );
    return Dem(
      elevation: Uint16List.fromList(buffer),
      rows: height,
      cols: width,
      west: (meta['west'] as num).toDouble(),
      south: (meta['south'] as num).toDouble(),
      east: (meta['east'] as num).toDouble(),
      north: (meta['north'] as num).toDouble(),
    );
  }

  double get pixelDegLat => (north - south) / rows;
  double get pixelDegLon => (east - west) / cols;

  /// Metres per pixel, north-south and east-west, at a given latitude.
  List<double> pixelSizeM(double lat) => [
        pixelDegLat * 111320.0,
        pixelDegLon * 111320.0 * math.cos(lat * math.pi / 180.0),
      ];

  bool contains(double lat, double lon) =>
      lat >= south && lat <= north && lon >= west && lon <= east;

  List<int> indexOf(double lat, double lon) {
    var row = ((north - lat) / pixelDegLat).round();
    var col = ((lon - west) / pixelDegLon).round();
    row = row < 0 ? 0 : (row >= rows ? rows - 1 : row);
    col = col < 0 ? 0 : (col >= cols ? cols - 1 : col);
    return [row, col];
  }

  double elevationAt(double lat, double lon) {
    final rc = indexOf(lat, lon);
    return elevation[rc[0] * cols + rc[1]].toDouble();
  }
}

/// An answer to "which way, and how high", with everything needed to judge it.
class Escape {
  final bool reachable;
  final double? targetLat;
  final double? targetLon;
  final double fromElevationM;
  final double? targetElevationM;
  final double? climbM;
  final double? distanceM;
  final double? bearingDeg;
  final String? compassName;
  final double riseM;
  final double resolutionM;
  final String reason;

  const Escape({
    required this.reachable,
    this.targetLat,
    this.targetLon,
    required this.fromElevationM,
    this.targetElevationM,
    this.climbM,
    this.distanceM,
    this.bearingDeg,
    this.compassName,
    required this.riseM,
    required this.resolutionM,
    required this.reason,
  });

  /// A deliberately slow estimate: 4 km/h flat, and uphill costs more.
  double? get walkMinutes {
    if (distanceM == null) return null;
    return (distanceM! + (climbM ?? 0) * climbPenalty) / (4000.0 / 60.0);
  }
}

/// Which way the ground rises, degrees clockwise from north, or null if it is flat.
double? uphillBearing(Dem dem, double lat, double lon, {int window = 2}) {
  final rc = dem.indexOf(lat, lon);
  final r0 = math.max(0, rc[0] - window);
  final r1 = math.min(dem.rows, rc[0] + window + 1);
  final c0 = math.max(0, rc[1] - window);
  final c1 = math.min(dem.cols, rc[1] + window + 1);
  if (r1 - r0 < 2 || c1 - c0 < 2) return null;

  // Mean gradient over the neighbourhood: north is -d/drow because row 0 is the northern edge.
  var sumNorth = 0.0;
  var sumEast = 0.0;
  var n = 0;
  for (var r = r0; r < r1; r++) {
    for (var c = c0; c < c1; c++) {
      final here = dem.elevation[r * dem.cols + c].toDouble();
      final below = r + 1 < dem.rows
          ? dem.elevation[(r + 1) * dem.cols + c].toDouble()
          : here;
      final above = r - 1 >= 0
          ? dem.elevation[(r - 1) * dem.cols + c].toDouble()
          : here;
      final rightC = c + 1 < dem.cols
          ? dem.elevation[r * dem.cols + (c + 1)].toDouble()
          : here;
      final leftC = c - 1 >= 0
          ? dem.elevation[r * dem.cols + (c - 1)].toDouble()
          : here;
      sumNorth += (below - above) / 2.0; // d/drow; south is positive
      sumEast += (rightC - leftC) / 2.0;
      n++;
    }
  }
  if (n == 0) return null;
  final size = dem.pixelSizeM(lat);
  final riseNorth = -(sumNorth / n) / size[0];
  final riseEast = (sumEast / n) / size[1];
  if (!riseNorth.isFinite || !riseEast.isFinite) return null;
  if (riseNorth.abs() < 1e-12 && riseEast.abs() < 1e-12) return null;
  return (math.atan2(riseEast, riseNorth) * 180.0 / math.pi + 360.0) % 360.0;
}

double angleBetween(double a, double b) => ((a - b + 180.0) % 360.0 - 180.0).abs();

/// Find ground that clears the expected rise, in a direction that goes uphill.
Escape planEscape(
  Dem dem,
  double lat,
  double lon, {
  double riseM = defaultRiseM,
  double maxWalk = maxWalkM,
  double maxTurnDeg = 75.0,
}) {
  final size = dem.pixelSizeM(lat);
  final resolution = math.max(size[0], size[1]);

  if (!dem.contains(lat, lon)) {
    return Escape(
      reachable: false,
      fromElevationM: double.nan,
      riseM: riseM,
      resolutionM: dem.pixelDegLat * 111320.0,
      reason: 'this point is outside the bundled DEM, so no escape can be planned',
    );
  }

  final origin = dem.indexOf(lat, lon);
  final here = dem.elevation[origin[0] * dem.cols + origin[1]].toDouble();
  final need = here + riseM + safetyMarginM;
  final up = uphillBearing(dem, lat, lon);

  var bestCost = double.infinity;
  int? bestRow;
  int? bestCol;
  var bestDistance = double.infinity;
  var bestClimb = 0.0;
  var bestBearing = 0.0;
  var nearestAny = double.infinity;
  var nearestAnyBearing = 0.0;
  var anyLower = false;

  for (var r = 0; r < dem.rows; r++) {
    final base = r * dem.cols;
    for (var c = 0; c < dem.cols; c++) {
      final elev = dem.elevation[base + c].toDouble();
      if (elev < need) continue;

      final dNorth = (r - origin[0]) * size[0];
      final dEast = (c - origin[1]) * size[1];
      final distance = math.sqrt(dNorth * dNorth + dEast * dEast);
      final bearing = (math.atan2(dEast, dNorth) * 180.0 / math.pi + 360.0) % 360.0;

      if (distance <= maxWalk) {
        if (up != null && angleBetween(bearing, up) > maxTurnDeg) {
          anyLower = true; // higher ground exists, but not uphill of here
        } else {
          final climb = elev - here;
          final cost = distance + climb * climbPenalty;
          if (cost < bestCost) {
            bestCost = cost;
            bestRow = r;
            bestCol = c;
            bestDistance = distance;
            bestClimb = climb;
            bestBearing = bearing;
          }
        }
      }
      if (distance < nearestAny) {
        nearestAny = distance;
        nearestAnyBearing = bearing;
      }
    }
  }

  // Final copies so the null check promotes: the loop assigns these, and promotion does not
  // survive that as reliably as it does for a final local.
  final row = bestRow;
  final col = bestCol;

  if (row == null || col == null) {
    final String reason;
    if (anyLower) {
      reason = 'the ground that clears ${riseM.toStringAsFixed(0)} m within walking '
          'distance is not uphill of you - it lies '
          '${nearestAnyBearing.toStringAsFixed(0)}°, across or down from where you are. '
          'Do not cross the water for it: climb the slope you are on, away from the stream';
    } else {
      reason = 'the nearest ground that clears ${riseM.toStringAsFixed(0)} m is '
          '${(nearestAny / 1000).toStringAsFixed(1)} km away, which is beyond what anyone '
          'covers on foot. Do not run for it: get to a solid multi-storey building and go to '
          'the highest floor you can reach';
    }
    return Escape(
      reachable: false,
      fromElevationM: here,
      distanceM: anyLower ? null : nearestAny,
      riseM: riseM,
      resolutionM: resolution,
      reason: reason,
    );
  }

  final tLat = dem.north - (row + 0.5) * dem.pixelDegLat;
  final tLon = dem.west + (col + 0.5) * dem.pixelDegLon;
  return Escape(
    reachable: true,
    targetLat: tLat,
    targetLon: tLon,
    fromElevationM: here,
    targetElevationM: dem.elevation[row * dem.cols + col].toDouble(),
    climbM: bestClimb,
    distanceM: bestDistance,
    bearingDeg: bestBearing,
    compassName: compass[compassIndex(bestBearing)],
    riseM: riseM,
    resolutionM: resolution,
    reason: 'uphill ground that clears the expected ${riseM.toStringAsFixed(0)} m rise by '
        '${safetyMarginM.toStringAsFixed(0)} m',
  );
}

// ---- spoken guidance -------------------------------------------------------------------------

/// One instruction, in both languages, with the numbers that produced it.
class Step {
  final String kind; // start | climb | hold | wrong_way | arrived | unreachable
  final String ne;
  final String en;
  final double? remainingM;
  final double? elevationNowM;

  const Step(this.kind, this.ne, this.en, {this.remainingM, this.elevationNowM});

  String spoken({String lang = 'ne'}) => lang == 'ne' ? ne : en;
}

/// Short, imperative, and correct. Kept as a table so a native speaker can review the whole
/// spoken vocabulary of the app in one place rather than hunting strings through the codebase.
///
/// These strings are pinned against the Python table by tests/test_dart_nepali_phrases.py, so
/// the two surfaces cannot drift into saying different things.
const Map<String, String> phrases = {
  'go_up': 'माथि जानुहोस्',
  'keep_up': 'अझ माथि जानुहोस्',
  'away_water': 'पानीबाट टाढा जानुहोस्',
  'wrong_way': 'तल जानुभयो — फर्कनुहोस्',
  'arrived': 'तपाईं सुरक्षित उचाइमा पुग्नुभयो',
  'no_ground': 'नजिकै सुरक्षित उचाइ छैन',
  'tall_building': 'अग्लो बहुतले भवनमा जानुहोस्',
  'top_floor': 'सक्दो माथिल्लो तल्लामा जानुहोस्',
  'dont_run': 'दौडन नखोज्नुहोस्',
  'hurry_careful': 'छिटो तर सावधान',
};

const Map<String, String> phrasesEn = {
  'go_up': 'Go up',
  'keep_up': 'Keep going up',
  'away_water': 'Get away from the water',
  'wrong_way': 'You are going down - turn back',
  'arrived': 'You have reached safe height',
  'no_ground': 'There is no safe high ground nearby',
  'tall_building': 'Get to a tall building',
  'top_floor': 'Go to the highest floor you can reach',
  'dont_run': 'Do not run for it',
  'hurry_careful': 'Quickly, but carefully',
};

/// The briefing, broken into short spoken instructions, most urgent first.
List<Step> steps(Escape e, {int limit = 5}) {
  final out = <Step>[];
  if (!e.reachable) {
    out.add(Step('unreachable', phrases['no_ground']!, phrasesEn['no_ground']!));
    out.add(Step('unreachable', phrases['dont_run']!, phrasesEn['dont_run']!));
    out.add(Step('unreachable', phrases['tall_building']!, phrasesEn['tall_building']!));
    out.add(Step('unreachable', phrases['top_floor']!, phrasesEn['top_floor']!));
    return out.take(limit).toList();
  }

  final dirNe = compassNe[compassIndex(e.bearingDeg!)];
  out.add(Step('climb', phrases['away_water']!, phrasesEn['away_water']!));
  out.add(Step('climb', '$dirNe तर्फ जानुहोस्', 'Head ${e.compassName}',
      remainingM: e.distanceM, elevationNowM: e.fromElevationM));
  out.add(Step(
      'climb',
      '${phrases['keep_up']} — करिब ${e.distanceM!.toStringAsFixed(0)} मिटर',
      '${phrasesEn['keep_up']} - about ${e.distanceM!.toStringAsFixed(0)} m',
      remainingM: e.distanceM));
  out.add(Step(
      'climb',
      'कम्तीमा ${e.targetElevationM!.toStringAsFixed(0)} मिटर उचाइमा पुग्नुहोस्',
      'Reach at least ${e.targetElevationM!.toStringAsFixed(0)} m elevation'));
  out.add(Step('climb', phrases['hurry_careful']!, phrasesEn['hurry_careful']!));
  return out.take(limit).toList();
}

double _metresBetween(double aLat, double aLon, double bLat, double bLon) {
  final dy = (bLat - aLat) * 111320.0;
  final dx = (bLon - aLon) * 111320.0 * math.cos(bLat * math.pi / 180.0);
  return math.sqrt(dy * dy + dx * dx);
}

/// The one line to say right now, from where the phone says the person is.
///
/// The ascent check is relative to where they started, never to the summit: someone who has
/// gained 20 m of a 200 m climb is doing the right thing and must not be told otherwise.
Step update(
  Escape e,
  Dem dem,
  double lat,
  double lon, {
  double? startedElevationM,
  double? lastElevationM,
  double arrivedSlackM = 1.0,
}) {
  final now = dem.elevationAt(lat, lon);
  final start = startedElevationM ?? now;

  if (!e.reachable) {
    return Step('unreachable', phrases['tall_building']!, phrasesEn['tall_building']!,
        elevationNowM: now);
  }

  if (e.targetElevationM != null && now >= e.targetElevationM! - arrivedSlackM) {
    return Step('arrived', phrases['arrived']!, phrasesEn['arrived']!,
        elevationNowM: now, remainingM: 0);
  }

  final remaining = _metresBetween(lat, lon, e.targetLat!, e.targetLon!);
  final reference = lastElevationM ?? start;

  // Losing height is the dangerous direction, and it is the one a panicking person takes without
  // noticing, because downhill is easier and faster.
  if (now < reference - 2.0) {
    return Step(
        'wrong_way',
        '${phrases['wrong_way']} — ${phrases['go_up']}',
        '${phrasesEn['wrong_way']} - go up',
        remainingM: remaining,
        elevationNowM: now);
  }

  if (now > reference + 1.0) {
    return Step(
        'climb',
        '${phrases['keep_up']} — करिब ${remaining.toStringAsFixed(0)} मिटर',
        '${phrasesEn['keep_up']} - about ${remaining.toStringAsFixed(0)} m to go',
        remainingM: remaining,
        elevationNowM: now);
  }

  return Step(
      'hold',
      '${phrases['go_up']} — ${remaining.toStringAsFixed(0)} मिटर',
      '${phrasesEn['go_up']} - ${remaining.toStringAsFixed(0)} m',
      remainingM: remaining,
      elevationNowM: now);
}

/// A full advisory sentence, wholly in Nepali including the direction word.
String adviceNe(Escape e) {
  if (!e.reachable) {
    return 'नजिकै सुरक्षित उचाइ छैन। पैदल पुग्न सकिने दूरीभित्र अनुमानित '
        '${e.riseM.toStringAsFixed(0)} मिटर माथिको जमिन छैन, वा त्यो दिशा माथि होइन। '
        'दौडन नखोज्नुहोस् — बलियो बहुतले भवन खोज्नुहोस् र सक्दो माथिल्लो तल्लामा जानुहोस्। '
        'पहिले खोलाबाट टाढा जानुहोस्। यो नक्सा करिब ${e.resolutionM.toStringAsFixed(0)} '
        'मिटरको ग्रिडमा आधारित छ, त्यसैले यसलाई क्षेत्रीय सुझाव मान्नुहोस् र स्थानीय '
        'निर्देशन पालना गर्नुहोस्।';
  }
  final dir = compassNe[compassIndex(e.bearingDeg!)];
  final climb = (e.climbM != null && e.climbM! > 1)
      ? ', करिब ${e.climbM!.toStringAsFixed(0)} मिटर माथि चढ्दै'
      : '';
  return '$dir तर्फ जानुहोस् — करिब ${e.distanceM!.toStringAsFixed(0)} मिटर$climb '
      '(पैदल करिब ${e.walkMinutes!.toStringAsFixed(0)} मिनेट)। '
      'तपाईं अहिले ${e.fromElevationM.toStringAsFixed(0)} मिटरमा हुनुहुन्छ। '
      'कम्तीमा ${e.targetElevationM!.toStringAsFixed(0)} मिटर उचाइमा पुग्नुहोस् — यसले '
      'अनुमानित ${e.riseM.toStringAsFixed(0)} मिटर पानीको सतहभन्दा माथि पुर्‍याउँछ। '
      'यो केवल भू-स्वरूपको जानकारी हो, ${e.resolutionM.toStringAsFixed(0)} मिटरको ग्रिडबाट — '
      'पुल, नाली वा पानी आफैं यसमा देखिँदैन। पहिले खोलाबाट टाढा जानुहोस्, त्यसपछि माथि।';
}

/// The caveat that travels with every answer, on screen and not only in a docstring.
const String terrainCaveat =
    'Terrain only, from a coarse national grid. It cannot see bridges, culverts, roads or the '
    'water. Move away from the stream first.';
