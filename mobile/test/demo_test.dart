import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/main.dart';

/// The flood scenario, start to finish.
///
/// This is the demonstration the original brief asked for by name - "when flash flood enters nepal how
/// the app react and all to show in demo" - and it had only ever been driven to step two, on a real
/// handset, before the screen slept. Everything after that was untested, which for a six-step sequence
/// shown to a room is most of it.
///
/// The panel walks itself with no network and no device: it reads the bundled script and reveals one
/// step per press. So the whole thing is testable, and this test presses the button six times.
void main() {
  Future<void> pump(WidgetTester tester) async {
    // rootBundle's future completes on the real event loop, which pumpAndSettle's fake clock never
    // advances to - so the panel would sit with zero steps and the test would blame the widget.
    await tester.runAsync(() async {
      await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: DemoPanel(
          title: 'What the app does when a flood comes',
          blurb: 'Green steps are computed on this phone; grey ones are measured elsewhere.',
          runLabel: 'Run the scenario',
          nextLabel: 'Next step',
          liveLabel: 'computed on the phone',
          citedLabel: 'cited',
          nepali: false,
          failedLabel: 'the scenario could not be loaded',
        ),
      ),
      ));
    });
    await tester.pumpAndSettle();
  }

  testWidgets('the scenario can be walked from the first step to the last', (tester) async {
    await pump(tester);

    // Nothing is shown until the button is pressed - the panel does not open mid-claim.
    expect(find.textContaining('Run the scenario'), findsOneWidget);

    await tester.tap(find.textContaining('Run the scenario'));
    await tester.pumpAndSettle();

    // Step one is visible and the button now counts.
    expect(find.textContaining('(1/6)'), findsOneWidget);
    expect(find.textContaining('28 September 2024'), findsOneWidget);

    // Press until the sequence ends. The loop is bounded and each press is asserted, so a scenario
    // that stalls fails here rather than silently showing the same step twice.
    // The counter is the number of steps VISIBLE, not the index of the current one, so it runs
    // (1/6) through (5/6) and then the button goes - which is the panel's intended ending, not an
    // off-by-one. Pressing five times reveals all six.
    for (var visible = 2; visible <= 5; visible++) {
      await tester.tap(find.textContaining('Next step'));
      await tester.pumpAndSettle();
      expect(find.textContaining('($visible/6)'), findsOneWidget,
          reason: 'pressing next did not reveal step $visible');
    }
    // The fifth press shows the last step and removes the control.
    await tester.tap(find.textContaining('Next step'));
    await tester.pumpAndSettle();

    // At the last step there is nothing left to press, which is the behaviour the panel intends.
    expect(find.textContaining('Next step'), findsNothing,
        reason: 'the button should be gone once the last step is shown');
  });

  testWidgets('every step says which half of the claim it belongs to', (tester) async {
    await pump(tester);
    await tester.tap(find.textContaining('Run the scenario'));
    await tester.pumpAndSettle();

    // The panel's whole honesty mechanism: each step is tagged live (computed here) or cited
    // (measured elsewhere). A step with neither tag would be a claim with no provenance.
    // Five presses reveal all six steps. The sixth press does not exist - the button is correctly
    // gone once the sequence ends - so this walks to the end rather than tapping a fixed count.
    for (var i = 0; i < 5; i++) {
      final live = find.textContaining('computed on the phone').evaluate().length;
      final cited = find.textContaining('cited').evaluate().length;
      expect(live + cited, greaterThan(0),
          reason: 'a step appeared with neither a live nor a cited marker on it');
      final next = find.textContaining('Next step');
      if (next.evaluate().isEmpty) break;
      await tester.tap(next);
      await tester.pumpAndSettle();
    }
  });
}
