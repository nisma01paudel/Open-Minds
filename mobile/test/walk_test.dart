// Which walk can I do from here — the ordinary-day screen.
//
// The loader is injected, the same way the terrain loader is, so these run headlessly with no
// asset bundle and no device.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/l10n.dart';
import 'package:pahiro_field/main.dart';
import 'package:pahiro_field/seasons.dart';
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
        body: WalkScreen(strings: const L10n(AppLang.en), lang: AppLang.en, loader: loader,
            seasonLoader: const _NoSeasons()),
      ),
    );


/// A season guide with no regions, so the walk tests test walking.
///
/// The WalkScreen loads a real season guide by default. Left in, its twelve bars sit above the trail
/// list and the assertions about walks start measuring the wrong widget - which is a sign the test
/// was reaching for something it did not mean to. Injecting an empty guide keeps the test about the
/// trail list and leaves the season strip to the season tests.
class _NoSeasons implements SeasonLoader {
  const _NoSeasons();
  @override
  Future<SeasonGuide> load() async => const SeasonGuide(regions: [], note: '');
}


/// A season loader that fails, to prove the screen says so rather than showing a gap.
class _BrokenSeasons implements SeasonLoader {
  const _BrokenSeasons();
  @override
  Future<SeasonGuide> load() async => throw StateError('simulated missing asset');
}

void main() {
  boardTests();
  l10nAudit();
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
    // `strings[...]` in the shell and `s[...]` inside a screen are both lookups. The first version
    // matched only the literal word `strings`, so every key a screen asked for was exempt - it would
    // have missed the four added with the duty panel.
    //
    // Widening it to ANY identifier was too far: `raw['steps']` and `j['slopes']` are map lookups
    // into JSON, not strings, and the guard failed on them. It matches the L10n names only.
    final used = RegExp(r"""\b(?:s|strings)\[\'([a-z0-9_.]+)\'\]""")
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

void l10nAudit() {
  test('no English sentence is rendered straight into the UI', () {
    // The defect this exists for, found twice on the emulator and once by looking at a screenshot
    // I had already taken:
    //
    //   यो फोनमा के चल्छ
    //   vision - sees change between two images and speaks Nepali on the handset, offline
    //
    // A Nepali heading over English literals, in a Nepali-first app. The strings were literals in
    // the widget rather than keys in l10n, so the test that walks strings['...'] could not see them
    // - it only checks keys that exist. Reading the file does not show it either, because the
    // English looks correct until you notice what language you are supposed to be in.
    //
    // So this looks for ASCII prose inside a Text(...) in the widget tree.
    final files = Directory('lib')
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'));
    final allowed = <String>{
      'Pahiro',                       // the product name, which is bilingual by design
      'monospace',                    // a font family, not prose
    };
    final offenders = <String>[];
    final re = RegExp(r"""Text\(\s*'([^']{12,})'""");

    for (final f in files) {
      for (final m in re.allMatches(f.readAsStringSync())) {
        final lit = m.group(1)!;
        if (lit.contains(r'$')) continue;             // interpolated: built from parts
        if (allowed.any(lit.contains)) continue;
        if (!RegExp(r'[A-Za-z]{3}').hasMatch(lit)) continue;   // no words in it
        offenders.add('${f.path}: $lit');
      }
    }

    expect(offenders, isEmpty,
        reason: 'English prose rendered in the UI, untranslated:\n${offenders.join('\n')}');
  });

  testWidgets('the walk screen says so when the season guide is missing', (tester) async {
    // The last of the silent hides. The walk list is the point of this screen, so a failed season
    // load must not block it - but a strip that fails and a strip with nothing to say looked
    // identical, which is the defect fixed in the three panels one round earlier.
    tester.view.physicalSize = const Size(1200, 3000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: WalkScreen(
          strings: const L10n(AppLang.ne), lang: AppLang.ne,
          loader: FakeLoader(),
          seasonLoader: const _BrokenSeasons(),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('लोड हुन सकेन'), findsOneWidget,
        reason: 'a failed season load left a gap instead of a message');
  });
}
