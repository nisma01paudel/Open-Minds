import 'dart:async';

import 'package:flutter/material.dart';

import 'theme.dart';

/// Hold to raise the alarm.
///
/// The reference app on this phone opens its emergency flow with a red "HOLD FOR EMERGENCY SOS -
/// notifies local dispatch authorities instantly" bar, then a countdown that can be cancelled. The
/// countdown is the right idea and is copied: an alarm that fires on a stray tap in a pocket is worse
/// than one that takes a deliberate press.
///
/// WHAT IS DELIBERATELY DIFFERENT, AND WHY
///
/// That promise cannot be kept here. Notifying dispatch requires a network, and this app exists for the
/// hours when there is none - it is offline-first by design, its whole data set ships inside it, and
/// its one radio feature is a Bluetooth advertisement. An SOS button that said "notifies authorities"
/// on a phone with no signal would be the single most dangerous sentence in the app: a person in rising
/// water would believe help had been called.
///
/// So this does the three things that genuinely work with the network already gone, in the order they
/// work:
///
///   1. puts the frame on the air over Bluetooth, so any handset in range carries it onward
///   2. shows which way to go and how high, computed on the phone
///   3. opens the share sheet, so the moment a signal returns the message is one tap from being sent
///
/// And it says all of that in the interface rather than implying it.
class SosPanel extends StatefulWidget {
  final String title;
  final String hold;
  final String sendingIn;
  final String cancel;
  final String offlineTruth;

  /// Called when the countdown completes. The caller owns the beacon and the share sheet, because
  /// those live on other screens.
  final Future<void> Function()? onFire;

  const SosPanel({
    super.key,
    required this.title,
    required this.hold,
    required this.sendingIn,
    required this.cancel,
    required this.offlineTruth,
    this.onFire,
  });

  @override
  State<SosPanel> createState() => _SosPanelState();
}

class _SosPanelState extends State<SosPanel> {
  static const _seconds = 5;

  Timer? _timer;
  int _left = 0;
  bool _armed = false;
  bool _fired = false;

  bool get _counting => _left > 0;

  void _begin() {
    if (_counting || _fired) return;
    setState(() => _left = _seconds);
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      if (_left <= 1) {
        t.cancel();
        setState(() {
          _left = 0;
          _fired = true;
        });
        widget.onFire?.call();
      } else {
        setState(() => _left -= 1);
      }
    });
  }

  void _cancelAll() {
    _timer?.cancel();
    setState(() {
      _left = 0;
      _armed = false;
      _fired = false;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final alarm = _counting || _fired;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: alarm ? const Color(0xFF7F1D1D) : const Color(0xFFB91C1C),
        borderRadius: BorderRadius.circular(PahiroTheme.radiusCard),
        boxShadow: const [
          BoxShadow(color: Color(0x33B91C1C), blurRadius: 18, offset: Offset(0, 6)),
        ],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(13),
            ),
            child: const Icon(Icons.sos, color: Colors.white, size: 23),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _counting
                  ? '${widget.sendingIn} $_left'
                  : (_fired ? widget.title.toUpperCase() : widget.title.toUpperCase()),
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14.5,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.0,
                  height: 1.2),
            ),
          ),
        ]),

        // The countdown is drawn, not just counted - a bar that empties is readable at a glance in the
        // conditions this screen is for.
        if (_counting) ...[
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _left / _seconds,
              minHeight: 7,
              backgroundColor: Colors.white.withValues(alpha: 0.18),
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ),
        ],

        const SizedBox(height: 12),
        Text(
          // The honest sentence, and it is the point of the whole panel.
          widget.offlineTruth,
          style: TextStyle(
              color: Colors.white.withValues(alpha: 0.88), fontSize: 12, height: 1.4),
        ),

        const SizedBox(height: 14),
        if (!alarm)
          GestureDetector(
            onTapDown: (_) => setState(() => _armed = true),
            onTapUp: (_) {
              setState(() => _armed = false);
              _begin();
            },
            onTapCancel: () => setState(() => _armed = false),
            child: Container(
              height: 52,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(PahiroTheme.radiusButton),
                border: Border.all(
                    color: _armed ? const Color(0xFFFCA5A5) : Colors.transparent, width: 3),
              ),
              child: Text(widget.hold,
                  style: const TextStyle(
                      color: Color(0xFFB91C1C), fontSize: 15, fontWeight: FontWeight.w800)),
            ),
          )
        else
          Row(children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _cancelAll,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white, width: 1.5),
                ),
                child: Text(widget.cancel),
              ),
            ),
          ]),
      ]),
    );
  }
}
