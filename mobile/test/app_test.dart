import 'dart:io';
import 'package:pahiro_field/duty.dart';

// The screens, and the first thing anyone sees: choose a language.
//
// A foreigner opens this app in Nepal and the first screen is in Nepali, or a Nepali speaker
// opens it and every instruction is in English at the moment they are least able to translate.
// Both are avoidable, so these tests hold the gate in place.

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/escape.dart' as escape;
import 'package:pahiro_field/l10n.dart';
import 'package:pahiro_field/main.dart';
import 'package:pahiro_field/offline_ai.dart' as ai;

/// A ramp rising east, centred on Melamchi - which is the place the screen defaults to.
///
/// It must cover that coordinate or the planner correctly refuses with "outside the bundled
/// DEM", and the test then asserts against a refusal while believing it is testing a plan. That
/// is exactly the mistake this file made the first time: the ramp was built around 85.0/27.0 and
/// the default place is 85.57/27.83.
escape.Dem rampDem() {
  const rows = 40;
  const cols = 40;
  final grid = Uint16List(rows * cols);
  for (var c = 0; c < cols; c++) {
    for (var r = 0; r < rows; r++) {
      grid[r * cols + c] = 1000 + c * 10;
    }
  }
  return escape.Dem(
    elevation: grid,
    rows: rows,
    cols: cols,
    west: 85.50, // Melamchi is at 85.57, so it sits inside this grid
    south: 27.78, // and at 27.83
    east: 85.70,
    north: 27.98,
  );
}

class FakeDemLoader implements DemLoader {
  final escape.Dem? dem;
  const FakeDemLoader(this.dem);
  @override
  Future<escape.Dem?> load() async => dem;
}

Widget app({AppLang? lang, escape.Dem? dem}) => PahiroApp(
      controller: LanguageController(lang),
      speaker: const SilentSpeaker(),
      demLoader: FakeDemLoader(dem),
    );

/// Pump the escape tab and press the plan button.
///
/// The default test surface is 800x600 and this screen is a scrolling list, so the button sits
/// below the fold unless the viewport is enlarged - a tap that misses is a silently passing
/// alternative to the test failing, which is the worst outcome for a screen about to be demoed
/// to a room.
Future<void> tapPlan(WidgetTester tester, escape.Dem? dem) async {
  tester.view.physicalSize = const Size(1000, 2200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(app(lang: AppLang.en, dem: dem));
  await tester.pumpAndSettle();

  final button = find.text('WHERE DO I GO FROM HERE?');
  expect(button, findsOneWidget, reason: 'the plan button must be present');
  await tester.ensureVisible(button);
  await tester.pumpAndSettle();
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  dutyPanelTests();
  group('the language gate', () {
    testWidgets('is the first screen when no language has been chosen', (tester) async {
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      expect(find.text('पहिरो · Pahiro'), findsOneWidget);
      // both languages are offered, each named in its own script
      expect(find.text('नेपाली   ·   Nepali'), findsOneWidget);
      expect(find.text('English   ·   English'), findsOneWidget);
      // and the escape tab is not reachable until a choice is made
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('the whole gate is readable in both languages at once', (tester) async {
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      // The tagline and the hint are shown in both scripts, because the reader has not yet
      // told us which one they read.
      expect(find.textContaining('कहाँ भाग्ने'), findsOneWidget);
      expect(find.textContaining('Which way to run'), findsOneWidget);
    });

    testWidgets('choosing Nepali opens the app in Nepali', (tester) async {
      final controller = LanguageController();
      await tester.pumpWidget(PahiroApp(
        controller: controller,
        speaker: const SilentSpeaker(),
        demLoader: const FakeDemLoader(null),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('नेपाली   ·   Nepali'));
      await tester.pumpAndSettle();

      expect(controller.value, AppLang.ne);
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('भाग्नुहोस्'), findsWidgets, reason: 'the tabs must be in Nepali');
      expect(find.text('Escape'), findsNothing);
    });

    testWidgets('choosing English opens the app in English', (tester) async {
      final controller = LanguageController();
      await tester.pumpWidget(PahiroApp(
        controller: controller,
        speaker: const SilentSpeaker(),
        demLoader: const FakeDemLoader(null),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('English   ·   English'));
      await tester.pumpAndSettle();

      expect(controller.value, AppLang.en);
      expect(find.text('Escape'), findsWidgets);
      expect(find.text('भाग्नुहोस्'), findsNothing);
    });

    testWidgets('a language already chosen skips the gate entirely', (tester) async {
      await tester.pumpWidget(app(lang: AppLang.en));
      await tester.pumpAndSettle();
      expect(find.text('पहिरो · Pahiro'), findsNothing);
      expect(find.byType(NavigationBar), findsOneWidget);
    });

    testWidgets('the language can be changed afterwards in settings', (tester) async {
      await tester.pumpWidget(app(lang: AppLang.en));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      expect(find.byType(RadioListTile<AppLang>), findsNWidgets(2));

      await tester.tap(find.text('नेपाली  ·  Nepali'));
      await tester.pumpAndSettle();
      expect(find.text('सेटिङ'), findsWidgets, reason: 'settings must follow the choice');
    });
  });

  group('the escape screen', () {
    testWidgets('says so when the elevation data is missing, and does not crash', (tester) async {
      await tapPlan(tester, null);
      expect(find.textContaining('did not load'), findsOneWidget);
    });

    testWidgets('on a ramp rising east it answers EAST and shows the height', (tester) async {
      await tapPlan(tester, rampDem());

      expect(find.textContaining('EAST'), findsWidgets);
      expect(find.textContaining('m →'), findsOneWidget, reason: 'from-height → target-height');
      expect(find.textContaining('Terrain only'), findsOneWidget,
          reason: 'the limitation must travel with the answer');
    });

    testWidgets('the spoken line is Nepali even when the UI is English', (tester) async {
      await tapPlan(tester, rampDem());

      // The instruction that has to be followed is Nepali regardless of the interface language:
      // it is what the person will hear, and "माथि जानुहोस्" is shorter than any translation.
      expect(find.text(escape.phrases['away_water']!), findsWidgets);
      // textContaining, because the keep_up step carries the remaining distance after it.
      expect(find.textContaining(escape.phrases['keep_up']!), findsWidgets);
    });

    testWidgets('flat ground refuses and says what to do instead', (tester) async {
      final flat = escape.Dem(
        elevation: Uint16List(40 * 40)..fillRange(0, 40 * 40, 100),
        rows: 40,
        cols: 40,
        west: 85.50,
        south: 27.78,
        east: 85.70,
        north: 27.98,
      );
      await tapPlan(tester, flat);

      expect(find.textContaining('NO REACHABLE HIGH GROUND'), findsWidgets);
      // Twice, deliberately: once inside the full Nepali sentence and once as a spoken step.
      expect(find.textContaining('दौडन नखोज्नुहोस्'), findsWidgets,
          reason: 'the Nepali refusal must tell them not to run for it');
    });
  });

  group('the other tabs', () {
    testWidgets('the beacon tab builds a real 20-byte frame and relays it', (tester) async {
      await tester.pumpWidget(app(lang: AppLang.en));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Beacon'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Build a sample frame'));
      await tester.pumpAndSettle();

      expect(find.textContaining('20 bytes'), findsOneWidget);
      expect(find.textContaining('spare of 24'), findsOneWidget);
      expect(find.textContaining('2 people'), findsOneWidget);
      expect(find.textContaining('relayed once'), findsOneWidget);
    });

    testWidgets('the board is honest about being empty', (tester) async {
      await tester.pumpWidget(app(lang: AppLang.en));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Board'));
      await tester.pumpAndSettle();
      expect(find.text('Nothing yet.'), findsOneWidget);
    });

    testWidgets('settings states that nothing life-saving needs a model', (tester) async {
      await tester.pumpWidget(app(lang: AppLang.en));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      // the default assumed handset is modest, so a tier is shown rather than the floor; the
      // claim under test is that the ladder resolves and the UI states the rule.
      expect(find.textContaining('needs ~'), findsOneWidget);
    });
  });

  group('the offline claim, as the tests see it', () {
    test('nothing that saves a life is behind the AI', () {
      expect(ai.lifesaving.difference(ai.tierNone.enables), isEmpty);
      expect(ai.tierNone.weightsMb, 0);
      for (final tier in ai.ladder) {
        expect(ai.lifesaving.difference(tier.enables), isEmpty,
            reason: '${tier.name} dropped a life-saving capability');
      }
    });

    test('the ladder is ordered by cost, largest first', () {
      final sizes = ai.ladder.map((t) => t.weightsMb).toList();
      final ascending = [...sizes]..sort();
      expect(sizes, ascending.reversed.toList());
    });
  });
}

// ---------------------------------------------------------------------------------------------
// The draft complaint, tapped BY NAME rather than by pixel.
// ---------------------------------------------------------------------------------------------

class _FixtureDuty implements DutyLoader {
  const _FixtureDuty();
  @override
  Future<DutyIndex> load() async => DutyIndex.parse(
      File('assets/complaint-index.json').readAsStringSync());
}

Widget _dutyPanel(AppLang lang) => MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: DutyPanel(
            strings: 'x', lat: 27.7047, lon: 85.3146,
            title: L10n(lang)['duty.title'],
            caption: L10n(lang)['duty.where'],
            noAddress: L10n(lang)['duty.noAddress'],
            defaultNote: L10n(lang)['duty.default'],
            draftButton: L10n(lang)['duty.draft'],
            letterNote: L10n(lang)['duty.letterNote'],
            nepali: lang == AppLang.ne,
            failedLabel: L10n(lang)['load.failed'],
            loader: const _FixtureDuty(),
          ),
        ),
      ),
    );

class _BrokenDuty implements DutyLoader {
  const _BrokenDuty();
  @override
  Future<DutyIndex> load() async => throw StateError('simulated missing asset');
}

void dutyPanelTests() {

  testWidgets('the draft complaint opens when its button is pressed', (tester) async {
    // Four attempts to press this button on the emulator all missed, because it sits below three
    // other panels and its y-coordinate moves with the content above it while I read the position
    // off a scaled screenshot. That is a bad instrument, not bad luck: a test that taps a widget BY
    // NAME cannot miss, and it runs in a second without a device.
    //
    // The panel is pumped directly with a fixture loader, because it reads its own asset and
    // rootBundle does not resolve assets inside a widget test - which is itself the reason the panel
    // is injectable now.
    tester.view.physicalSize = const Size(1200, 3000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_dutyPanel(AppLang.ne));
    await tester.pumpAndSettle();

    final button = find.text('उजुरीको मस्यौदा देखाउनुहोस्');
    expect(button, findsOneWidget, reason: 'the draft button did not render');

    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();

    // The letter itself - the thing four emulator attempts never captured.
    expect(find.textContaining('धारा १२(२)(ग)'), findsOneWidget,
        reason: 'the draft did not open, or it does not cite the section');
    expect(find.textContaining('स्वचालित रूपमा तयार भएको'), findsOneWidget,
        reason: 'the letter must say it was drafted automatically');
    expect(find.textContaining('वडा समिति'), findsWidgets,
        reason: 'the Nepali office name is not in the letter');
    expect(button, findsOneWidget, reason: 'pressing it should not remove the control');
  });

  testWidgets('the duty holder is Nepali in the Nepali interface', (tester) async {
    tester.view.physicalSize = const Size(1200, 3000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_dutyPanel(AppLang.ne));
    await tester.pumpAndSettle();

    expect(find.textContaining('वडा समिति'), findsOneWidget,
        reason: 'the office is not shown in Nepali');
    expect(find.textContaining('Ward Committee under the Ward Chair'), findsNothing,
        reason: 'the English office string is rendered in the Nepali interface');
  });

  testWidgets('a panel whose data is missing says so instead of disappearing', (tester) async {
    // Three panels used to return an empty box when their asset failed, which is indistinguishable
    // from having nothing to say. The project's whole argument is that a user must be able to tell
    // "nothing is here" from "we could not look" - and that has to hold for the app's own furniture,
    // not only for the map data.
    tester.view.physicalSize = const Size(1200, 3000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    const label = 'यो भाग लोड हुन सकेन';
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: DutyPanel(
          strings: 'x', lat: 27.7047, lon: 85.3146, title: 't', caption: 'c',
          noAddress: 'n', defaultNote: 'd', draftButton: 'b', letterNote: 'l',
          nepali: true, failedLabel: label, loader: const _BrokenDuty(),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('लोड हुन सकेन'), findsOneWidget,
        reason: 'a failed load rendered nothing at all');
  });
}
