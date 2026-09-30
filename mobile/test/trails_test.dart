// Trails on the handset.
//
// The expected numbers are the Python side's own output for the same query, so this is a parity
// check as well as a unit test: two implementations of one dataset in two languages drift, and a
// trail that is 4.0 km in the browser and 6.1 km on the phone is a bug nobody notices until a
// walker does.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/trails.dart';

void main() {
  late TrailNetwork net;

  setUpAll(() {
    final bytes = File('assets/trails.geojson').readAsBytesSync();
    net = TrailNetwork.fromBytes(bytes);
  });

  test('the bundled network loads at the scale the data has', () {
    expect(net.trails.length, 23726);
    expect(net.attribution, contains('OpenStreetMap'));
    expect(net.attribution, contains('ODbL'));
  });

  test('nearby trails agree with the Python engine on distance', () {
    // Python: trails.nearby(net, 85.3620, 27.7750, radius_m=3000, limit=3, dem=None)
    //
    //   nearest-to-point:  2066.3 m   2297.4 m   1755.3 m
    //
    // These match EXACTLY, which is the part that matters: the same haversine, the same points,
    // the same answer about whether a trail is near you.
    final got = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 3);
    expect(got.length, 3);
    expect(got[0].nearestM, closeTo(2066.3, 1.0));
    expect(got[1].nearestM, closeTo(2297.4, 1.0));
    expect(got[2].nearestM, closeTo(1755.3, 1.0));
    expect(got[1].name, startsWith('Shiva puri peak trek'));
  });

  test('length differs from Python by the amount junction snapping removes, and no more', () {
    // Python reports 6192.5 / 4031.7 / 3941.6 m; Dart reports 6472.6 / 4253.6 / 4020.7 m.
    //
    // They are measuring different things and both are right for their purpose. Python walks the
    // SNAPPED GRAPH, where vertices within 25 m of each other are merged into one junction - so
    // the sum of its edges is slightly shorter than the drawn line. Dart measures the DRAWN LINE,
    // which is the truer length of the trail a person walks.
    //
    // The test asserts the size of the gap rather than pretending it is not there: if the
    // difference ever grows past a few per cent, something has changed and nobody would see it.
    final got = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 3);
    const pythonLengths = [6192.5, 4031.7, 3941.6];
    for (var i = 0; i < 3; i++) {
      final gap = (got[i].lengthM - pythonLengths[i]) / pythonLengths[i];
      expect(gap, greaterThan(0), reason: 'the drawn line should be the longer of the two');
      expect(gap, lessThan(0.08),
          reason: 'snapping removed more than 8% of trail $i, which is a bug not a rounding');
    }
  });

  test('the longest trail comes first, not the nearest', () {
    final got = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 8);
    for (var i = 1; i < got.length; i++) {
      expect(got[i - 1].lengthM, greaterThanOrEqualTo(got[i].lengthM));
    }
  });

  test('only trails actually within the radius are returned', () {
    final got = net.nearby(85.3620, 27.7750, radiusM: 1500, limit: 20);
    for (final t in got) {
      expect(t.nearestM, lessThanOrEqualTo(1500));
    }
  });

  test('a point in the middle of the ocean returns nothing rather than a guess', () {
    expect(net.nearby(0.0, 0.0, radiusM: 1000).isEmpty, isTrue);
  });

  test('an unnamed path is labelled as one rather than given an invented name', () {
    final got = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 8);
    final unnamed = got.where((t) => t.name.isEmpty);
    expect(unnamed, isNotEmpty);
    expect(unnamed.first.label, '(unnamed path)');
  });

  test('the walk time is a real figure, not a placeholder', () {
    final got = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 3);
    for (final t in got) {
      // 4-6 km at 5 km/h is roughly 50-75 minutes
      expect(t.flatMinutes, greaterThan(20));
      expect(t.flatMinutes, lessThan(200));
    }
  });

  test('fragments shorter than the minimum are not offered as a walk', () {
    // The bundle keeps every way - Python counts all 23,726 - and the minimum is applied when a
    // walk is OFFERED, not when the data is read.
    expect(net.trails.length, 23726);
    final offered = net.nearby(85.3620, 27.7750, radiusM: 3000, limit: 50);
    expect(offered, isNotEmpty);
    for (final t in offered) {
      expect(t.lengthM, greaterThanOrEqualTo(minTrailM));
    }
  });

  test('the bundle is byte-identical to the one the web app serves', () {
    // Copied, not regenerated. If these ever diverge, the phone and the browser disagree about
    // where a path goes - and nobody would find out until a walker did.
    final mobile = File('assets/trails.geojson').readAsBytesSync();
    final web = File('../web/public/data/trails.geojson').readAsBytesSync();
    expect(mobile.length, web.length);
    expect(const Utf8Encoder().convert(utf8.decode(mobile)), equals(web));
  });
}
