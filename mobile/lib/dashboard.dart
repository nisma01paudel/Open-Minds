import 'package:flutter/material.dart';

import 'theme.dart';

/// The dashboard furniture, taken from the reference app on the same phone.
///
/// Yatra Sathi's home screen is a greeting, one card carrying a single large number with a bar under
/// it, and then a grid of services - two to a row, each with a tinted rounded icon, a bold name and a
/// muted line. Pahiro had the capabilities and none of the presentation: everything was a paragraph
/// inside a card, so nothing was scannable and nothing said where to start.
///
/// These are the two pieces that do the work.
///
/// WHY A GRID RATHER THAN A LIST
///
/// Because the app now has eight surfaces and a person opens it while it is raining. A list of eight
/// is a menu; a grid of eight with distinct colours is a thing you can find something in without
/// reading. That is the whole reason the reference uses one.
class ServiceCard extends StatelessWidget {
  final IconData icon;
  final Color tint;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool wide;

  const ServiceCard({
    super.key,
    required this.icon,
    required this.tint,
    required this.title,
    required this.subtitle,
    this.onTap,
    this.wide = false,
  });

  @override
  Widget build(BuildContext context) {
    final body = Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PahiroTheme.surface,
        borderRadius: BorderRadius.circular(PahiroTheme.radiusCard),
        border: Border.all(color: PahiroTheme.hairline),
        boxShadow: const [
          BoxShadow(color: Color(0x0A111827), blurRadius: 12, offset: Offset(0, 3)),
        ],
      ),
      child: wide
          ? Row(children: [
              _disc(),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: _titleStyle),
                  const SizedBox(height: 4),
                  Text(subtitle, style: _subStyle),
                ]),
              ),
              const Icon(Icons.chevron_right, color: PahiroTheme.inkMuted, size: 20),
            ])
          : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _disc(),
              const SizedBox(height: 10),
              Text(title, style: _titleStyle),
              const SizedBox(height: 3),
              Text(subtitle, style: _subStyle),
            ]),
    );

    return onTap == null
        ? body
        : InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(PahiroTheme.radiusCard),
            child: body,
          );
  }

  /// The tinted rounded square. Square rather than circular, at the reference's proportion - a circle
  /// reads as an avatar and a square reads as a tool.
  Widget _disc() => Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          color: tint.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(13),
        ),
        child: Icon(icon, color: tint, size: 23),
      );

  static const _titleStyle = TextStyle(
      color: PahiroTheme.ink, fontSize: 15, fontWeight: FontWeight.w700, height: 1.2);
  static const _subStyle =
      TextStyle(color: PahiroTheme.inkMuted, fontSize: 12, height: 1.3);
}

/// The one number the app is actually about, with a bar under it.
///
/// The reference leads with "Nepal Visa Tracker - TIME REMAINING 47 Days" and a progress bar. Pahiro
/// has exactly one comparable figure and it was three screens deep in a paragraph: how many documented
/// slopes are at or above the rainfall threshold today. That belongs at the top, in the largest type
/// on the screen, because it is the reason somebody opened the app.
class StatusCard extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  final String note;
  final double fraction;
  final Color accent;
  final IconData icon;

  const StatusCard({
    super.key,
    required this.label,
    required this.value,
    required this.unit,
    required this.note,
    required this.fraction,
    required this.accent,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(PahiroTheme.radiusCard),
        boxShadow: const [
          BoxShadow(color: Color(0x33111827), blurRadius: 18, offset: Offset(0, 6)),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: accent, size: 21),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(label.toUpperCase(),
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.4)),
          ),
        ]),
        const SizedBox(height: 16),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(value,
                  style: TextStyle(
                      color: accent,
                      fontSize: 34,
                      fontWeight: FontWeight.w800,
                      height: 1.0,
                      letterSpacing: -1)),
              const SizedBox(height: 2),
              Text(unit,
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.55),
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600)),
            ]),
          ),
        ]),
        const SizedBox(height: 14),
        // The bar is not decoration: it is the same fraction the number states, drawn, so the shape of
        // the day reads before the digits do.
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: fraction.clamp(0.0, 1.0),
            minHeight: 7,
            backgroundColor: Colors.white.withValues(alpha: 0.10),
            valueColor: AlwaysStoppedAnimation<Color>(accent),
          ),
        ),
        const SizedBox(height: 10),
        Text(note,
            style: TextStyle(
                color: Colors.white.withValues(alpha: 0.62), fontSize: 11.5, height: 1.35)),
      ]),
    );
  }
}

/// The letter-spaced capitals the reference puts above a group.
class SectionLabel extends StatelessWidget {
  final String text;
  const SectionLabel(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 10),
        child: Text(text.toUpperCase(),
            style: const TextStyle(
                color: PahiroTheme.inkMuted,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.5)),
      );
}
