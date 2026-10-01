import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/duty.dart';
import 'package:pahiro_field/places.dart';
import 'package:pahiro_field/trails.dart';

/// The app reads three bundled files with its own parsers. Nothing checked that the keys those
/// parsers ask for are the keys the files actually carry - and for the trail bundle they were not.
///
///     name:       props['n'] ?? ''
///     difficulty: props['d'] ?? 'not recorded'
///
/// The shipped file carries `h` and `r` and nothing else. So all 23,726 trails came out with an empty
/// name and the fallback difficulty, and the Walk screen printed "(unnamed path)" and "not recorded"
/// on every row while the real highway type sat unread. Sixty-eight tests passed throughout.
///
/// This is the guard against that whole class: parse the REAL files, and fail if a field the reader
/// depends on comes back empty or at its fallback.
void main() {
  final data = Directory('../web/public/data');

  test('the trail bundle yields a type for every trail', () {
    final f = File('${data.path}/trails.geojson');
    expect(f.existsSync(), isTrue, reason: 'the bundle this app ships must be present');

    final net = TrailNetwork.parse(f.readAsStringSync());
    expect(net.trails, isNotEmpty);

    final untyped = net.trails.where((t) => t.highway.isEmpty).length;
    expect(untyped, 0,
        reason: '$untyped of ${net.trails.length} trails carry no highway type, which means the '
            'parser is reading a key the file does not have - the exact bug this test exists for');

    // The types that actually occur, so a parser that reads the wrong key cannot pass by accident.
    final kinds = net.trails.map((t) => t.highway).toSet();
    expect(kinds, contains('path'));
    expect(kinds.length, greaterThan(1), reason: 'a single type would suggest a constant, not a read');
  });

  test('the places bundle yields a name and a position for every unit', () {
    final f = File('${data.path}/places.geojson');
    final parsed = PlaceList.parse(f.readAsStringSync());
    expect(parsed.all, isNotEmpty);
    for (final p in parsed.all) {
      expect(p.name, isNotEmpty, reason: 'an unread name key renders as a blank row');
      expect(p.lat, isNot(0.0), reason: 'an unread lat key puts every unit at null island');
    }
  });

  test('the duty bundle yields a title and an office for every slope', () {
    final f = File('${data.path}/complaint-index.json');
    final idx = DutyIndex.parse(f.readAsStringSync());
    expect(idx.slopes, isNotEmpty);
    expect(idx.resolved, greaterThan(0),
        reason: 'counts.resolved is rendered as a bare number; a wrong key would show 0 and look plausible');
    for (final d in idx.slopes) {
      expect(d.title, isNotEmpty);
      expect(d.office, isNotEmpty);
    }
  });

  test('the demo script carries both languages for every step', () {
    // The scenario is read aloud to a room. A step with no Nepali would fall back to an empty string
    // on the Nepali build and look like a rendering fault rather than a missing key.
    final j = json.decode(File('${data.path}/demo-script.json').readAsStringSync()) as Map;
    final steps = j['steps'] as List;
    expect(steps.length, 6);
    for (final s in steps) {
      final m = s as Map;
      expect(m['en'], isNotEmpty);
      expect(m['ne'], isNotEmpty);
      expect(m['n'], isNotNull);
    }
  });

  test('the seasons bundle carries twelve months per region', () {
    final j = json.decode(File('${data.path}/seasons.json').readAsStringSync()) as Map;
    final regions = j['regions'];
    final list = regions is Map ? regions.values.toList() : regions as List;
    expect(list, isNotEmpty);
    for (final r in list) {
      final months = (r as Map)['months'] as List;
      expect(months.length, 12, reason: 'the strip draws one bar per month');
      for (final m in months) {
        expect((m as Map)['month'], isNotNull);
      }
    }
  });
}
