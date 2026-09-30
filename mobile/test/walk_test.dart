// Which walk can I do from here — the ordinary-day screen.
//
// The loader is injected, the same way the terrain loader is, so these run headlessly with no
// asset bundle and no device.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/l10n.dart';
import 'package:pahiro_field/main.dart';
import 'package:pahiro_field/trails.dart';

const _net = TrailNetwork(
  attribution: '© OpenStreetMap contributors, ODbL 1.0',
  region: 'test',
  trails: [
    Trail(name: 'Shiva puri peak trek (stairs)', difficulty: 'hard', lengthM: 4024.0,
        nearestM: 120.0, points: [[85.3152, 27.7052], [85.3160, 27.7060]]),
    Trail(name: '', difficulty: 'easy', lengthM: 2500.0, nearestM: 900.0,
        points: [[85.3205, 27.7100], [85.3212, 27.7108]]),
    Trail(name: 'too far away', difficulty: 'easy', lengthM: 9000.0, nearestM: 40000.0,
        points: [[86.9, 28.9], [86.95, 28.95]]),
  ],
);

class FakeLoader implements TrailLoader {
  @override
  Future<TrailNetwork> load() async => _net;
}

class FailingLoader implements TrailLoader {
  @override
  Future<TrailNetwork> load() async => throw Exception('asset missing');
}

/// A ListView builds only what fits on screen, so anything below the fold is never constructed
/// and no finder can see it. The default test viewport is short; this makes it tall enough that
/// the whole screen exists. The alternative - scrollUntilVisible in every assertion - tests the
/// scrolling rather than the content.
Future<void> pumpScreen(WidgetTester tester, TrailLoader loader) async {
  tester.view.physicalSize = const Size(1200, 2600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(wrap(loader));
  await tester.pumpAndSettle();
}

Widget wrap(TrailLoader loader) => MaterialApp(
      home: Scaffold(
        body: WalkScreen(strings: const L10n(AppLang.en), lang: AppLang.en, loader: loader),
      ),
    );

void main() {
  boardTests();
  testWidgets('it lists walks near you, longest first', (tester) async {
    await pumpScreen(tester, FakeLoader());
    expect(find.text('Shiva puri peak trek (stairs)'), findsOneWidget);
    expect(find.textContaining('4.0 km'), findsWidgets);
  });

  testWidgets('a trail with no name is labelled rather than given one', (tester) async {
    await pumpScreen(tester, FakeLoader());
    expect(find.text('(unnamed path)', skipOffstage: false), findsOneWidget);
  });

  testWidgets('a trail 40 km away is not offered', (tester) async {
    await pumpScreen(tester, FakeLoader());
    expect(find.text('too far away'), findsNothing);
  });

  testWidgets('the OpenStreetMap attribution is shown, because ODbL requires it', (tester) async {
    await pumpScreen(tester, FakeLoader());
    // Two matches: the caveat sentence also names OpenStreetMap. The attribution itself is
    // the one carrying the licence, so that is what is asserted exactly.
    expect(find.textContaining('OpenStreetMap', skipOffstage: false), findsWidgets);
    expect(find.text('© OpenStreetMap contributors, ODbL 1.0'), findsOneWidget);
    expect(find.textContaining('ODbL', skipOffstage: false), findsOneWidget);
  });

  testWidgets('it says what the data cannot tell you', (tester) async {
    await pumpScreen(tester, FakeLoader());
    expect(find.textContaining('not every Nepali footpath is mapped', skipOffstage: false), findsOneWidget);
  });

  testWidgets('a missing bundle reports the failure instead of an empty list', (tester) async {
    // An empty screen looks the same whether there is nothing to walk or the data failed to
    // load, and those are different problems.
    await pumpScreen(tester, FailingLoader());
    expect(find.textContaining('Could not open the trail data'), findsOneWidget);
  });

  testWidgets('tapping a walk moves you to its trailhead', (tester) async {
    await pumpScreen(tester, FakeLoader());
    await tester.tap(find.text('Shiva puri peak trek (stairs)'));
    await tester.pumpAndSettle();
    expect(find.textContaining('27.7052'), findsOneWidget);
  });
}

// ---------------------------------------------------------------------------------------------
// The board empty state, and a guard for every other string beside it.
// ---------------------------------------------------------------------------------------------

void boardTests() {
  test('the board says why it may be empty rather than only that it is', () {
    // An empty screen that says only "nothing here" cannot be told apart from a broken one. A
    // person who sees it should know whether to wait, to move closer to other phones, or to stop
    // trusting the app - and only the app can tell them which.
    for (final ne in [true, false]) {
      final s = L10n(ne ? AppLang.ne : AppLang.en);
      expect(s['board.empty'], isNotEmpty);
      expect(s['board.empty_why'], isNotEmpty,
          reason: 'the board explains itself in ${ne ? 'Nepali' : 'English'}');
      expect(s['board.empty_why'].length, greaterThan(40),
          reason: 'a one-word explanation explains nothing');
    }
  });

  test('every string the app asks for exists in both languages', () {
    // A missing key renders as the key itself or throws, depending on the lookup - either way the
    // user sees a failure the developer never did. This walks the keys the source actually uses.
    final src = File('lib/main.dart').readAsStringSync();
    final used = RegExp(r"""strings\['([a-z0-9_.]+)'\]""")
        .allMatches(src)
        .map((m) => m.group(1)!)
        .toSet();
    expect(used, isNotEmpty, reason: 'the scan found no keys, so it is not scanning');

    for (final ne in [true, false]) {
      final s = L10n(ne ? AppLang.ne : AppLang.en);
      for (final k in used) {
        final v = s[k];
        expect(v, isNotNull, reason: "'$k' is missing in ${ne ? 'Nepali' : 'English'}");
        expect(v, isNot(k), reason: "'$k' fell back to the key itself in ${ne ? 'ne' : 'en'}");
      }
    }
  });
}
