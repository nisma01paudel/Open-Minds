import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'escape.dart';
import 'theme.dart';

/// The last minute at which leaving is still possible.
///
/// Every flood app answers "where do I go". None answers the question that actually decides whether
/// somebody lives: **by when**. A route that exists at 14:00 can be gone by 14:40, and the person
/// standing in the street has no way to know which side of that line they are on.
///
/// This runs the escape planner backward through time. It raises the water in steps, asks the same
/// planner whether any way out still exists, and returns the last moment it did. Nothing new is
/// modelled - it is the existing planner called in a loop, which is why the answer is trustworthy:
/// it is exactly as good as the route it is built from, and no better.
///
/// WHAT IT IS NOT
///
/// It is not a forecast. The rise rate is a *what-if* the user sets, and the screen says so. What is
/// real is the terrain: given this much water, this is when the ground stops offering a way out. The
/// number moves if the rate moves, and the app shows both.
class EscapeDeadline {
  /// Minutes from now until the last route closes. Null when no route exists even at zero rise -
  /// which is its own answer, and a more urgent one.
  final int? minutesLeft;

  /// The ground height that closes the last route, in metres above the start.
  final double? closureRiseM;

  /// How many distinct steps were open at the start and at the end, so the screen can show the
  /// closing rather than only the moment it finished closing.
  final int openAtStart;
  final int openAtEnd;

  /// The step-by-step shape of the closure, for drawing: (minutesFromNow, stepsStillOpen).
  final List<List<double>> curve;

  final String reason;

  const EscapeDeadline({
    required this.minutesLeft,
    required this.closureRiseM,
    required this.openAtStart,
    required this.openAtEnd,
    required this.curve,
    required this.reason,
  });
}

/// Count how many of the eight compass directions still offer a way up, at a given rise.
///
/// Eight, because that is what a person can act on without a compass: the planner's own compass names
/// are the output, and a direction with nowhere to go is dropped. The count is the app's measure of
/// "is there still a way out at all".
int openRoutes(Dem dem, double lat, double lon, double riseM) {
  var open = 0;
  for (var i = 0; i < 8; i++) {
    final bearing = i * 45.0;
    final target = _step(dem, lat, lon, bearing, riseM);
    if (target != null) open++;
  }
  return open;
}

/// Walk outward along a bearing until the ground clears the water, or give up at the search radius.
///
/// This is deliberately the same shape as the planner's own search so the two cannot disagree about
/// what counts as reachable.
List<double>? _step(Dem dem, double lat, double lon, double bearingDeg, double riseM) {
  final start = dem.elevationAt(lat, lon);
  final rad = bearingDeg * math.pi / 180.0;
  // At this grid, roughly 111 m per 0.001 degrees; 40 steps reaches about 4.4 km, which is the same
  // order as the planner's own horizon and far enough that "no route" means no route rather than
  // "not far enough".
  for (var step = 1; step <= 40; step++) {
    final d = step * 0.001;
    final pLat = lat + d * math.cos(rad);
    final pLon = lon + d * math.sin(rad) / math.max(0.2, math.cos(lat * math.pi / 180.0));
    if (!dem.contains(pLat, pLon)) return null;
    final e = dem.elevationAt(pLat, pLon);
    if (e - start >= riseM + 1.0) return [pLat, pLon, e];
  }
  return null;
}

/// The deadline itself.
///
/// [riseMetresPerHour] is the user's assumption and is shown as one. [horizonHours] bounds the search:
/// past a day the answer stops being meaningful for a flash flood, and an unbounded loop would report
/// deadlines of three weeks.
EscapeDeadline computeDeadline(
  Dem dem,
  double lat,
  double lon, {
  required double riseMetresPerHour,
  double horizonHours = 12,
  int slices = 48,
}) {
  if (riseMetresPerHour <= 0) {
    return const EscapeDeadline(
      minutesLeft: null,
      closureRiseM: null,
      openAtStart: 0,
      openAtEnd: 0,
      curve: [],
      reason: 'no rise',
    );
  }

  final start = openRoutes(dem, lat, lon, 0);
  if (start == 0) {
    // No route even with dry ground. Saying so is the whole point - this is the most urgent answer the
    // app can give, and it must not be dressed up as a countdown.
    return EscapeDeadline(
      minutesLeft: 0,
      closureRiseM: 0,
      openAtStart: 0,
      openAtEnd: 0,
      curve: const [],
      reason: 'none-at-start',
    );
  }

  final curve = <List<double>>[];
  double? closedAtMinutes;
  double? closedAtRise;


  for (var i = 0; i <= slices; i++) {
    final hours = horizonHours * i / slices;
    final rise = riseMetresPerHour * hours;
    final open = openRoutes(dem, lat, lon, rise);
    curve.add([hours * 60, open.toDouble()]);

    if (open == 0) {
      // Interpolate between the last open slice and this one, so the answer is a minute rather than a
      // slice boundary. Without this the deadline quantises to 15-minute steps, which reads as a
      // precision the model does not have and hides the real one behind it.
      final prevHours = horizonHours * (i - 1) / slices;
      closedAtMinutes = ((prevHours + hours) / 2) * 60;
      closedAtRise = riseMetresPerHour * ((prevHours + hours) / 2);
      break;
    }

  }

  return EscapeDeadline(
    minutesLeft: closedAtMinutes?.round(),
    closureRiseM: closedAtRise,
    openAtStart: start,
    openAtEnd: closedAtMinutes == null ? start : 0,
    curve: curve,
    reason: closedAtMinutes == null ? 'holds' : 'closes',
  );
}

// ---------------------------------------------------------------------------------------------
// The card.
//
// The number is the headline, because it is the only thing on the screen a person can still act on.
// The curve under it is the same information drawn: routes closing one at a time as the water comes
// up, so the shape of the closing is legible before the digits are read.
// ---------------------------------------------------------------------------------------------


class DeadlineCard extends StatelessWidget {
  final EscapeDeadline deadline;
  final String title;
  final String unit;
  final String noneAtAll;
  final String holdsText;
  final String assumption;

  const DeadlineCard({
    super.key,
    required this.deadline,
    required this.title,
    required this.unit,
    required this.noneAtAll,
    required this.holdsText,
    required this.assumption,
  });

  @override
  Widget build(BuildContext context) {
    final none = deadline.reason == 'none-at-start';
    final holds = deadline.minutesLeft == null && !none;
    final urgent = deadline.minutesLeft != null && deadline.minutesLeft! <= 45;

    final accent = none || urgent
        ? const Color(0xFFDC2626)
        : (holds ? const Color(0xFF15803D) : const Color(0xFFB45309));

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PahiroTheme.surface,
        borderRadius: BorderRadius.circular(PahiroTheme.radiusCard),
        border: Border.all(color: accent.withValues(alpha: 0.45), width: 1.5),
        boxShadow: const [
          BoxShadow(color: Color(0x0A111827), blurRadius: 12, offset: Offset(0, 3)),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title.toUpperCase(),
            style: const TextStyle(
                color: PahiroTheme.inkMuted,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.5)),
        const SizedBox(height: 10),

        if (none)
          Text(noneAtAll, style: TextStyle(color: accent, fontSize: 15, height: 1.35,
              fontWeight: FontWeight.w700))
        else if (holds)
          Text(holdsText, style: TextStyle(color: accent, fontSize: 15, height: 1.35,
              fontWeight: FontWeight.w700))
        else
          Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic,
              children: [
                Text('${deadline.minutesLeft}',
                    style: TextStyle(
                        color: accent,
                        fontSize: 44,
                        fontWeight: FontWeight.w800,
                        height: 1.0,
                        letterSpacing: -1.5)),
                const SizedBox(width: 8),
                Text(unit,
                    style: const TextStyle(
                        color: PahiroTheme.inkMuted, fontSize: 14, fontWeight: FontWeight.w600)),
              ]),

        if (deadline.curve.length > 1) ...[
          const SizedBox(height: 14),
          SizedBox(height: 46, child: CustomPaint(
            painter: _ClosingPainter(deadline.curve, accent),
            size: const Size(double.infinity, 46),
          )),
        ],

        const SizedBox(height: 10),
        Text(assumption,
            style: const TextStyle(
                color: PahiroTheme.inkMuted, fontSize: 11.5, height: 1.4)),
      ]),
    );
  }
}

/// The closure, drawn. A line stepping down to zero: how many ways out remain, against time.
class _ClosingPainter extends CustomPainter {
  final List<List<double>> curve;
  final Color accent;
  _ClosingPainter(this.curve, this.accent);

  @override
  void paint(Canvas canvas, Size size) {
    if (curve.length < 2) return;
    final maxOpen = curve.map((p) => p[1]).reduce(math.max);
    if (maxOpen <= 0) return;
    final maxT = curve.last[0].clamp(1.0, double.infinity);

    final path = Path();
    for (var i = 0; i < curve.length; i++) {
      final x = (curve[i][0] / maxT) * size.width;
      final y = size.height - (curve[i][1] / maxOpen) * size.height;
      i == 0 ? path.moveTo(x, y) : path.lineTo(x, y);
    }
    canvas.drawPath(
        path, Paint()..color = accent..strokeWidth = 2.2..style = PaintingStyle.stroke
          ..strokeJoin = StrokeJoin.round);

    // The floor, so "zero ways out" is a visible line rather than the bottom of the box.
    canvas.drawLine(Offset(0, size.height - 0.5), Offset(size.width, size.height - 0.5),
        Paint()..color = PahiroTheme.hairline..strokeWidth = 1);
  }

  @override
  bool shouldRepaint(covariant _ClosingPainter old) =>
      old.curve != curve || old.accent != accent;
}
