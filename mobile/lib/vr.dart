import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:sensors_plus/sensors_plus.dart';

/// Looking at the valley through the phone, with your head instead of your finger.
///
/// The brief asked for this by name - "keep VR feature also to see how it looks the real valley" -
/// and what existed was a panorama you drag sideways. That is a picture you scroll, not somewhere you
/// look. This turns the phone into the window: the gyroscope drives the view, so turning your head
/// turns the valley, and the same frame goes to both eyes for a cardboard viewer.
///
/// WHAT THIS IS HONESTLY NOT
///
/// It is **monoscopic**. There is one equirectangular image, so both eyes receive the same pixels and
/// there is no depth - which is exactly what every 360-degree photo viewer does, and it is not the
/// same thing as stereo VR. Claiming otherwise would be the kind of thing this project exists to
/// refuse, so the screen says it in as many words.
///
/// It also **drifts**. `sensors_plus` exposes raw gyroscope rates and no fused orientation, so yaw and
/// pitch are integrated: every small bias error accumulates and the horizon slowly slides. A recenter
/// control is therefore not a nicety, it is load-bearing, and it is on screen at all times.
class VrPanorama extends StatefulWidget {
  final String asset;
  final String title;
  final String hint;

  /// Supplied by the caller: this widget owns no language.
  final String monoscopicNote;
  final String recenter;
  final String noGyro;
  final String close;

  /// How much of the panorama is visible at once. 0.5 shows half a turn, which is a natural window
  /// on a phone held at arm's length.
  final double fieldOfView;

  const VrPanorama({
    super.key,
    required this.asset,
    required this.title,
    required this.hint,
    required this.monoscopicNote,
    required this.recenter,
    required this.noGyro,
    required this.close,
    this.fieldOfView = 0.5,
  });

  @override
  State<VrPanorama> createState() => _VrPanoramaState();
}

class _VrPanoramaState extends State<VrPanorama> {
  StreamSubscription<GyroscopeEvent>? _sub;
  Timer? _decay;

  /// Radians. Yaw wraps, pitch is clamped - you cannot look further up than straight up.
  double yaw = 0;
  double pitch = 0;
  bool gyroWorking = false;

  @override
  void initState() {
    super.initState();
    _startGyro();
  }

  void _startGyro() {
    try {
      _sub = gyroscopeEventStream().listen(
        (e) {
          if (!mounted) return;
          setState(() {
            gyroWorking = true;
            // The stream is radians per second; a 60 Hz sensor means multiplying by roughly the
            // frame interval. Negative because turning the phone right should move the view right.
            yaw -= e.y * 0.016;
            pitch += e.x * 0.016;
            pitch = pitch.clamp(-1.2, 1.2);
            if (yaw > math.pi) yaw -= 2 * math.pi;
            if (yaw < -math.pi) yaw += 2 * math.pi;
          });
        },
        onError: (_) => mounted ? setState(() => gyroWorking = false) : null,
        cancelOnError: false,
      );
    } catch (_) {
      gyroWorking = false;
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    _decay?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(children: [
        // Two eyes, side by side. Each gets the same pixels because there is only one image - the
        // honest version of "VR" that a single panorama can support.
        Row(children: [
          Expanded(child: _eye(left: true)),
          Container(width: 2, color: Colors.black),
          Expanded(child: _eye(left: false)),
        ]),

        // Everything the viewer needs to know, over the image and small, because a VR screen that
        // fills with text is not a VR screen.
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Container(
            color: const Color(0xCC000000),
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 14),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(widget.monoscopicNote,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10, height: 1.35)),
              const SizedBox(height: 6),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                OutlinedButton(
                  onPressed: () => setState(() { yaw = 0; pitch = 0; }),
                  child: Text(widget.recenter),
                ),
                const SizedBox(width: 10),
                OutlinedButton(
                  onPressed: () => Navigator.of(context).maybePop(),
                  child: Text(widget.close),
                ),
              ]),
            ]),
          ),
        ),

        if (!gyroWorking)
          Positioned(
            left: 12,
            right: 12,
            top: 40,
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xEECD5C0F),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(widget.noGyro,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white, fontSize: 11, height: 1.35)),
            ),
          ),
      ]),
    );
  }

  /// One eye. The panorama is 2:1, so at this viewport's height it is twice as wide as it is tall -
  /// which is why the offset is computed as a fraction of [widthTimes] rather than of the width.
  Widget _eye({required bool left}) {
    return LayoutBuilder(builder: (context, box) {
      final h = box.maxHeight;
      final w = box.maxWidth;
      final panoW = h * 2; // 2:1 equirectangular

      // Inter-eye separation. Small, and only horizontal: with one image there is no real parallax,
      // and a large offset would look like a misaligned picture rather than depth.
      final eyeShift = left ? -0.004 : 0.004;

      // Yaw is a fraction of a full turn. The panorama's left edge is yaw = -pi.
      var frac = (yaw / (2 * math.pi)) + 0.5 + eyeShift;
      frac = frac % 1.0;

      final maxOffset = panoW - w;
      final offset = (frac * panoW).clamp(0.0, maxOffset);

      // Pitch slides the image vertically. The panorama is only as tall as the viewport, so there is
      // little to slide into; a small parallax reads as looking up and down without exposing an edge.
      final vShift = -pitch * h * 0.18;

      return ClipRect(
        child: Stack(children: [
          Positioned(
            left: -offset,
            top: vShift,
            width: panoW,
            height: h * 1.25,
            child: Image.asset(
              widget.asset,
              fit: BoxFit.fill,
              errorBuilder: (_, _, _) => Container(
                color: const Color(0xFF0B1220),
                alignment: Alignment.center,
                child: Text(widget.hint,
                    style: const TextStyle(color: Color(0xFF64748B), fontSize: 11)),
              ),
            ),
          ),
          // A faint horizon line: in a monoscopic view it is the only thing that makes the pitch
          // change legible, and it is the first thing a viewer notices missing.
          Positioned(
            left: 0,
            right: 0,
            top: h / 2 + vShift,
            child: Container(height: 1, color: const Color(0x33FFFFFF)),
          ),
        ]),
      );
    });
  }
}
