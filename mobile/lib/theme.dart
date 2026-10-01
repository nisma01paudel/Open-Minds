import 'package:flutter/material.dart';

/// The app's look, taken from a Nepali app that gets it right.
///
/// Pahiro was dark navy with small type and tight spacing - legible underground, and plain next to
/// anything modern. Yatra Sathi, on the same phone, is the reference: a near-white ground, one deep
/// indigo for anything you press, large bold headings over muted grey subtitles, and generous corner
/// radii with soft shadows so every surface looks like a card rather than a panel.
///
/// The palette below is read off that app's own screens rather than invented, because the point is to
/// look like the thing the user pointed at.
///
/// ONE THING IS DELIBERATELY NOT COPIED
///
/// Yatra Sathi's ground is a warm near-white. This app has to be readable by a person standing in the
/// rain at night holding a phone at arm's length, so the page ground stays slightly cool and the
/// contrast ratios are higher than that reference's. Beauty that costs legibility in the one moment
/// this app exists for would be the wrong trade.
class PahiroTheme {
  // --- the palette, from the reference ---
  static const ground = Color(0xFFF6F7FB); // page
  static const surface = Color(0xFFFFFFFF); // card
  static const primary = Color(0xFF3D4EB0); // deep indigo - buttons, links, focus
  static const primarySoft = Color(0xFFE9EAFB); // the tinted circle behind an icon
  static const ink = Color(0xFF111827); // headings
  static const inkMuted = Color(0xFF6B7280); // subtitles and captions
  static const hairline = Color(0xFFE5E7EB); // dividers and card edges

  // --- status, kept legible on a light ground and meaningful to this app ---
  static const danger = Color(0xFFB91C1C);
  static const warn = Color(0xFFB45309);
  static const safe = Color(0xFF15803D);
  static const info = Color(0xFF0369A1);

  static const radiusCard = 16.0;
  static const radiusButton = 26.0;

  static ThemeData light() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: ground,
      colorScheme: base.colorScheme.copyWith(
        primary: primary,
        surface: surface,
        onPrimary: Colors.white,
        onSurface: ink,
        error: danger,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: ground,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
            color: ink, fontSize: 19, fontWeight: FontWeight.w700, letterSpacing: -0.2),
        iconTheme: IconThemeData(color: ink),
      ),
      // A pill, with a shadow. This is the single component that carries the reference's whole feel.
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusButton)),
          textStyle: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700),
          elevation: 2,
          shadowColor: const Color(0x553D4EB0),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size.fromHeight(48),
          side: const BorderSide(color: primary, width: 1.4),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radiusButton)),
          textStyle: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          side: const BorderSide(color: hairline),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          borderSide: const BorderSide(color: hairline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          borderSide: const BorderSide(color: hairline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          borderSide: const BorderSide(color: primary, width: 1.6),
        ),
      ),
      sliderTheme: base.sliderTheme.copyWith(
        activeTrackColor: primary,
        thumbColor: primary,
        inactiveTrackColor: primarySoft,
      ),
      dividerTheme: const DividerThemeData(color: hairline, thickness: 1, space: 1),
      // Large headings over muted subtitles: the reference's clearest habit, and the one that most
      // changes how finished a screen looks.
      textTheme: base.textTheme
          .copyWith(
            displaySmall: const TextStyle(
                color: ink, fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: -0.6, height: 1.15),
            headlineSmall: const TextStyle(
                color: ink, fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: -0.3, height: 1.2),
            titleMedium: const TextStyle(color: ink, fontSize: 16, fontWeight: FontWeight.w700),
            bodyMedium: const TextStyle(color: ink, fontSize: 14.5, height: 1.45),
            bodySmall: const TextStyle(color: inkMuted, fontSize: 12.5, height: 1.4),
            labelSmall: const TextStyle(
                color: inkMuted, fontSize: 10.5, fontWeight: FontWeight.w700, letterSpacing: 1.1),
          )
          .apply(bodyColor: ink, displayColor: ink),
    );
  }

  /// The section divider the reference uses: letter-spaced capitals with a rule either side.
  ///
  /// Worth a widget rather than a TextStyle because it does real work - it tells a reader that the
  /// thing below it is a different KIND of thing from the thing above, which on this app is the
  /// difference between advice the phone computed and a measurement somebody else made.
  static Widget rule(String label) => Row(children: [
        const Expanded(child: Divider()),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(label.toUpperCase(), style: const TextStyle(
              color: inkMuted, fontSize: 10.5, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
        ),
        const Expanded(child: Divider()),
      ]);

  /// A card with the reference's proportions: a soft tinted disc, a bold line, a muted line.
  static Widget card({required Widget child, EdgeInsets? padding}) => Container(
        padding: padding ?? const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: surface,
          borderRadius: BorderRadius.circular(radiusCard),
          border: Border.all(color: hairline),
          boxShadow: const [BoxShadow(color: Color(0x0A111827), blurRadius: 12, offset: Offset(0, 3))],
        ),
        child: child,
      );

  /// The tinted circle an icon sits in - the reference's most recognisable detail, and cheap.
  static Widget disc(IconData icon, {double size = 64, Color? tint}) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(color: tint ?? primarySoft, shape: BoxShape.circle),
        child: Icon(icon, color: primary, size: size * 0.44),
      );
}
