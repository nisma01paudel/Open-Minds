// When to go, on the phone - and the two things the data insists on being honest about.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/seasons.dart';

void main() {
  final guide = SeasonGuide.parse(File('assets/seasons.json').readAsStringSync());

  test('all six regions arrive with twelve months each', () {
    expect(guide.regions.length, 6);
    for (final r in guide.regions) {
      expect(r.months.length, 12, reason: '${r.name} is missing months');
      expect(r.months.map((m) => m.month).toSet().length, 12,
          reason: '${r.name} has a duplicate month');
    }
  });

  test('only June to September claim to have been cross-checked', () {
    // The cross-check against this project's own CHIRPS measurement covers the monsoon window. A
    // phone that rendered twelve equally confident months would be overstating eight of them, and
    // the file marks which is which - so the phone must read the mark rather than the average.
    for (final r in guide.regions) {
      final validated = r.months.where((m) => m.validated).map((m) => m.month).toSet();
      expect(validated, {6, 7, 8, 9}, reason: '${r.name}: $validated');
    }
  });

  test('Kathmandu carries its failure rather than hiding it', () {
    // ERA5 puts nearly twice the measured monsoon on Kathmandu, so that region's rain figures must
    // not be quoted. If this ever flips, look at the check rather than assume it is broken.
    final k = guide.regions.firstWhere((r) => r.key == 'kathmandu');
    expect(k.reliable, isFalse, reason: 'the ERA5/CHIRPS disagreement was real');
    expect(k.verdict, contains('NOT reliable'));
  });

  test('the other regions say they passed, and say what they passed against', () {
    for (final r in guide.regions) {
      if (r.key == 'kathmandu') continue;
      expect(r.verdict, isNotEmpty, reason: '${r.name} carries no verdict at all');
    }
    expect(guide.regions.where((r) => r.reliable).length, 5);
  });

  test('nearest() picks the region you are actually in', () {
    expect(guide.nearest(27.7047, 85.3146)!.key, 'kathmandu');
    expect(guide.nearest(28.2096, 83.9856)!.key, 'annapurna');
    expect(guide.nearest(27.8069, 86.7140)!.key, 'khumbu');
  });

  test('driest and wettest are the extremes of the region, not the first and last', () {
    final k = guide.nearest(27.7047, 85.3146)!;
    expect(k.driest.rainMmPerDay, lessThan(k.wettest.rainMmPerDay));
    for (final m in k.months) {
      expect(m.rainMmPerDay, greaterThanOrEqualTo(k.driest.rainMmPerDay));
      expect(m.rainMmPerDay, lessThanOrEqualTo(k.wettest.rainMmPerDay));
    }
  });

  test('the guide does not call any month good or bad', () {
    // The file's own rule, carried into the app: a farmer, a trekker and a paraglider want
    // different weather from the same month, so the numbers are given and the decision is theirs.
    expect(guide.note, isNotEmpty);
    for (final r in guide.regions) {
      for (final m in r.months) {
        expect(m.name, isNot(contains('good')));
        expect(m.name, isNot(contains('best')));
      }
    }
  });
}
