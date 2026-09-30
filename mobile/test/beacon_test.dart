// Vectors derived from the Python reference implementation (src/pahiro/mesh/beacon.py).
// Do not edit by hand. They are pinned from the other side by
// tests/test_dart_beacon_vectors.py, which re-derives every value here from the Python
// source and fails if the two codecs have drifted - so hardcoded vectors cannot rot
// unnoticed while `flutter test` stays green.

import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/beacon.dart';

final DateTime when = DateTime.fromMillisecondsSinceEpoch(1790769600 * 1000, isUtc: true);

const List<List<String>> encoded = [
  ['typical sos', '23384df887e330002a4a5600822d22005b155074'],
  ['no position', '209bfbfbc5e2300000000000000000005b155048'],
  ['minimal', '20ad8bb2f800000000000000000000005b15508c'],
  ['maxed bits', '20ad8bb2f8fff00000000000000000005b155037'],
  ['negative longitude', '219066127fe1000027dc79ff8519cf005b155040'],
  ['southern hemisphere', '21b2af178ce210ffcc239300e66d32005b1550e8'],
  ['status kind', '294d9e367ae200002a445000822850005b155028'],
  ['utf8 id', '2113c2502ae220002b0b60008026e0005b15508e'],
];

/// null where the Python relay() also returns nothing - a frame out of hops.
const List<List<String?>> relayed = [
  ['typical sos', '23384df887c730002a4a5600822d22005b15501d'],
  ['no position', '209bfbfbc5c6300000000000000000005b155021'],
  ['minimal', null],
  ['maxed bits', '20ad8bb2f8dff00000000000000000005b1550c3'],
  ['negative longitude', '219066127fc5000027dc79ff8519cf005b155029'],
  ['southern hemisphere', '21b2af178cc610ffcc239300e66d32005b155081'],
  ['status kind', '294d9e367ac600002a445000822850005b155041'],
  ['utf8 id', '2113c2502ac620002b0b60008026e0005b1550e7'],
];

const List<List<Object>> truncations = [
  ['handset-7f3a', 14413],
  ['d1', 39931],
  ['x', 44427],
  ['gps-1', 36966],
  ['हाते-फोन', 5058],
  ['shesh-9f2c', 9028],
];

void main() {

  test('the frame is 20 bytes of the 24 a legacy advertisement allows', () {
    expect(encodedBytes, 20);
    expect(maxAdBytes, 24);
    expect(3 + 1 + 1 + 2 + maxAdBytes, 31);
  });

  test('truncate16 matches the Python reference exactly', () {
    for (final row in truncations) {
      expect(truncate16(row[0] as String), row[1] as int,
          reason: 'FNV-1a disagreement on ${row[0]}');
    }
  });

  test('encode produces byte-identical frames to the Python reference', () {
    for (final row in encoded) {
      final actual = hexOf(encodeFor(row[0]));
      expect(actual, row[1], reason: '${row[0]} encoded differently');
      expect(actual.length, encodedBytes * 2, reason: '${row[0]} is the wrong length');
    }
  });

  test('relay matches the Python reference byte for byte', () {
    for (var i = 0; i < encoded.length; i++) {
      final r = relay(_fromHex(encoded[i][1]));
      expect(r == null ? null : hexOf(r), relayed[i][1],
          reason: '${encoded[i][0]} relayed differently');
    }
  });

  test('a frame out of hops is not rebroadcast', () {
    expect(relay(encodeFor('minimal')), isNull);
  });

  test('a relay changes only ttl/hops and the CRC over them', () {
    final first = encodeFor('typical sos');
    final second = relay(first)!;
    final differing = <int>[];
    for (var i = 0; i < first.length; i++) {
      if (first[i] != second[i]) differing.add(i);
    }
    expect(differing, [5, 19]);
  });

  test('round trip recovers every field', () {
    final b = decode(encodeFor('typical sos'))!;
    expect(b.kind, 'sos');
    expect(b.severity, 'critical');
    expect(b.people, 3);
    expect(b.ttl, maxTtl);
    expect(b.hops, 0);
    expect(b.lowBattery, isTrue);
    expect(b.hasPosition, isTrue);
    expect(b.lat, closeTo(27.71542, 0.00002));
    expect(b.lon, closeTo(85.31234, 0.00002));
    expect(b.peopleText, '3 people');
    expect(b.created.millisecondsSinceEpoch, when.millisecondsSinceEpoch);
  });

  test('a phone with no fix can still call for help', () {
    final b = decode(encodeFor('no position'))!;
    expect(b.hasPosition, isFalse);
    expect(b.people, 3, reason: 'losing the fix must not lose the rest of the frame');
    expect(b.peopleText, '3 people');
    expect(b.severity, 'urgent');
  });

  test('people count covers unknown, one, many and overflow', () {
    expect(decode(encode('a', 'b', people: 0, when: when))!.peopleText,
        'unknown number of people');
    expect(decode(encode('a', 'b', people: 1, when: when))!.peopleText, '1 person');
    expect(decode(encode('a', 'b', people: 4, when: when))!.peopleText, '4 people');
    expect(decode(encode('a', 'b', people: 15, when: when))!.peopleText, '15+ people');
  });

  test('a single flipped bit in any byte is refused', () {
    final good = encodeFor('typical sos');
    for (var i = 0; i < good.length; i++) {
      for (final bit in [0x01, 0x10, 0x80]) {
        final bad = Uint8List.fromList(good);
        bad[i] ^= bit;
        expect(decode(bad), isNull, reason: 'byte $i bit $bit was accepted');
      }
    }
  });

  test('rubbish from the world is refused, never thrown', () {
    expect(decode(null), isNull);
    expect(decode(<int>[]), isNull);
    expect(decode(List<int>.filled(19, 0)), isNull);
    expect(decode(List<int>.filled(20, 0)), isNull);
    expect(decode(List<int>.filled(20, 255)), isNull);
    expect(decode(List<int>.generate(20, (i) => i)), isNull);
    expect(decode(List<int>.filled(40, 0)), isNull);
  });

  test('an unknown version is refused rather than guessed at', () {
    final f = Uint8List.fromList(encodeFor('minimal'));
    f[0] = (2 << 5) | (f[0] & 0x1F);
    f[19] = crc8(f.sublist(0, 19));
    expect(decode(f), isNull);
  });

  test('encoding refuses what would decode as something else', () {
    expect(() => encode('a', 'b', ttl: 8), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', hops: 9), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', people: 16), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', severity: 'very-bad'), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', kind: 'picnic'), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', lat: 27.7), throwsA(isA<BeaconError>()));
    expect(() => encode('a', 'b', lat: 91.0, lon: 85.0), throwsA(isA<BeaconError>()));
  });

  test('ttl is spent and the flood stops', () {
    var p = encode('a', 'b', ttl: 2, when: when);
    var hops = 0;
    while (true) {
      final n = relay(p);
      if (n == null) break;
      p = n;
      hops++;
      expect(hops, lessThanOrEqualTo(10), reason: 'the flood never stopped');
    }
    expect(hops, 2);
    expect(decode(p)!.ttl, 0);
    expect(relay(p), isNull);
  });

  test('a live beacon is not mistaken for a stale one', () {
    final b = decode(encodeFor('typical sos'))!;
    expect(b.isStale(now: when), isFalse);
    expect(b.isStale(now: when.add(const Duration(hours: 5))), isFalse);
    expect(b.isStale(now: when.add(const Duration(hours: 7))), isTrue);
    expect(b.isStale(now: when.subtract(const Duration(hours: 1))), isTrue);
  });

  test('the timestamp survives the wire across years', () {
    for (final years in [0, 1, 5, 20]) {
      final t = when.add(Duration(days: 365 * years));
      final b = decode(encode('a', 'b', when: t))!;
      expect(b.created.year, t.year, reason: 'year drift at +$years y');
    }
  });

  test('position quantisation is far finer than the 15 m search radius', () {
    final b = decode(encode('a', 'b', lat: 27.71542, lon: 85.31234, when: when))!;
    final latErrM = (b.lat! - 27.71542).abs() * 111320.0;
    final lonErrM = (b.lon! - 85.31234).abs() * 111320.0 * 0.883;
    expect(latErrM, lessThan(0.6));
    expect(lonErrM, lessThan(0.6));
  });

  test('a Flutter app can advertise where a browser cannot', () {
    expect(canAdvertise, isTrue);
  });
}

Uint8List _fromHex(String hex) => Uint8List.fromList([
      for (var i = 0; i < hex.length; i += 2)
        int.parse(hex.substring(i, i + 2), radix: 16),
    ]);

/// The frame for each named case, rebuilt here so encode() is exercised with the same inputs
/// the Python reference used.
Uint8List encodeFor(String name) {
  switch (name) {

    case 'typical sos':
      return encode('handset-7f3a', 'msg-abc123', kind: 'sos', lat: 27.71542, lon: 85.31234, people: 3, severity: 'critical', lowBattery: true, when: when);
    case 'no position':
      return encode('d1', 'm1', lat: null, lon: null, people: 3, when: when);
    case 'minimal':
      return encode('x', 'y', ttl: 0, hops: 0, severity: 'info', people: 0, when: when);
    case 'maxed bits':
      return encode('x', 'y', ttl: 7, hops: 7, severity: 'critical', people: 15, when: when);
    case 'negative longitude':
      return encode('gps-1', 'm-2', lat: 26.12345, lon: -80.54321, severity: 'concern', when: when);
    case 'southern hemisphere':
      return encode('gps-2', 'm-3', lat: -33.98765, lon: 151.01234, people: 1, when: when);
    case 'status kind':
      return encode('relay-9', 'm-9', kind: 'status', lat: 27.7, lon: 85.3, when: when);
    case 'utf8 id':
      return encode('हाते-फोन', 'सन्देश-१', lat: 28.2096, lon: 83.9856, people: 2, when: when);
    default:
      throw StateError('unknown case $name');
  }
}