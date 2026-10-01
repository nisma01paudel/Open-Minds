import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pahiro_field/l10n.dart';
import 'package:pahiro_field/main.dart';

/// The Board and Settings screens.
///
/// Both were fixed blind. The phone kept locking before I could reach either, so every change to them
/// was made against the source and the suite - and both had been shipping a defect that only a person
/// looking at the screen would have caught:
///
///   Settings rendered 'settings.title' and 'settings.language' as its headings, because four keys
///   were referenced by the widget and defined in neither language.
///
///   The Board said its emptiness meant 'nobody has sent one, or no other phone is close enough yet -
///   put phones near each other', while the widget takes a strings object and nothing else and the app
///   has no Bluetooth scanner. It could never fill, and the copy sent people to move their phones.
///
/// These tests render both screens and assert what a reader actually sees.
void main() {
  final en = L10n(AppLang.en);

  testWidgets('the board never shows a raw key or an unearned reason', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: BoardScreen(strings: en))));
    await tester.pumpAndSettle();

    final texts = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => t.data ?? '')
        .where((d) => d.isNotEmpty)
        .toList();

    expect(texts, isNotEmpty, reason: 'a blank screen cannot be told apart from a broken one');

    for (final t in texts) {
      expect(t.startsWith('board.'), isFalse,
          reason: 'the screen printed its own key name: "$t"');
    }

    // The claim that must not come back: this board cannot receive anything, so it must not tell a
    // reader that proximity would help.
    final joined = texts.join(' ').toLowerCase();
    expect(joined.contains('near each other'), isFalse,
        reason: 'the board is telling the user to move their phone closer, and no scanner exists');
    expect(joined.contains('not built'), isTrue,
        reason: 'the board must say plainly that the receiving half is missing');
  });

  testWidgets('the settings screen shows words, not key names', (tester) async {
    final controller = LanguageController();
    addTearDown(controller.dispose);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: SettingsScreen(strings: en, controller: controller)),
    ));
    await tester.pumpAndSettle();

    final texts = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => t.data ?? '')
        .where((d) => d.isNotEmpty)
        .toList();

    expect(texts, isNotEmpty);
    for (final t in texts) {
      // The whole defect: a label that is literally the lookup key it came from.
      expect(RegExp(r'^settings\.[a-zA-Z]+$').hasMatch(t), isFalse,
          reason: 'the screen printed its own key name: "$t"');
    }

    // And the words that should be there are.
    expect(texts.any((t) => t == en['settings.title']), isTrue);
    expect(texts.any((t) => t == en['settings.language']), isTrue);
    expect(texts.any((t) => t == en['settings.model']), isTrue);
  });

  testWidgets('the settings screen offers both languages by their own names', (tester) async {
    final controller = LanguageController();
    addTearDown(controller.dispose);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: SettingsScreen(strings: en, controller: controller)),
    ));
    await tester.pumpAndSettle();

    // A person who cannot read the current language has to be able to find their own - so the
    // endonym is shown, not just the English name.
    expect(find.textContaining('नेपाली'), findsOneWidget);
    expect(find.textContaining('English'), findsOneWidget);

    // Choosing one is a real state change, not a decoration.
    await tester.tap(find.textContaining('नेपाली'));
    await tester.pumpAndSettle();
    expect(controller.value, AppLang.ne);
  });
}
