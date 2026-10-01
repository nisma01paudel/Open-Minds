import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'escape.dart';

/// A hillshaded relief map, drawn on the phone from the elevation grid that already ships with it.
///
/// There was no map in this app at all. The brief asks for one - "from places map to major places
/// description it should be all there, the map should be precise" - and the data to draw one has been
/// in `assets/terrain.bin` since the beginning, used only to walk an escape route.
///
/// So this is not a tile client. It is a renderer: 832x512 cells of real AWS Terrain elevation,
/// shaded by computing the surface normal against a north-west light, coloured by height, and
/// uploaded once as a `ui.Image`. Nothing here touches the network, which is the point - the same
/// reason the tiles are bundled for the web build.
///
/// Cost is bounded deliberately. A 832x512 hillshade is 425,000 pixel evaluations, far too much to
/// do per frame, so the relief is computed ONCE per view at a size no larger than [resolution] and
/// cached. Panning rebuilds it; that is a deliberate trade because a moving map that stutters is
/// worse than one that redraws crisply.
class TerrainMap extends StatefulWidget {
  final Dem dem;

  /// Degrees. The point the map is centred on.
  final double lat;
  final double lon;

  /// How much ground to show, in degrees of latitude. The window is square in degrees, so the
  /// horizontal span is scaled by cos(lat) to keep the aspect honest.
  final double span;

  /// Drawn over the relief: usually the selected place.
  final List<MapMark> marks;

  /// A line to draw over the relief - the escape route. Latitude/longitude pairs.
  final List<List<double>>? route;

  /// Shown if the relief cannot be drawn. Supplied by the caller because this widget does not own
  /// the app's language, and an English sentence hardcoded here is exactly the kind of untranslated
  /// prose the l10n audit exists to catch.
  final String failureText;

  /// Longest edge of the generated relief, in pixels. 320 keeps a full rebuild under a few
  /// milliseconds on a 2021 mid-range phone while still looking like terrain rather than a blob.
  final int resolution;

  const TerrainMap({
    super.key,
    required this.dem,
    required this.lat,
    required this.lon,
    this.span = 0.6,
    this.marks = const [],
    this.route,
    this.resolution = 320,
    required this.failureText,
  });

  @override
  State<TerrainMap> createState() => _TerrainMapState();
}

/// Something to draw on the map. [kind] decides the colour and the shape.
class MapMark {
  final double lat;
  final double lon;
  final String label;
  final MapMarkKind kind;
  const MapMark(this.lat, this.lon, this.label, {this.kind = MapMarkKind.place});
}

enum MapMarkKind { place, slope, destination, you }

class _TerrainMapState extends State<TerrainMap> {
  ui.Image? _relief;
  bool _failed = false;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _build();
  }

  @override
  void didUpdateWidget(covariant TerrainMap old) {
    super.didUpdateWidget(old);
    if (old.lat != widget.lat ||
        old.lon != widget.lon ||
        old.span != widget.span ||
        !identical(old.dem, widget.dem)) {
      _build();
    }
  }

  @override
  void dispose() {
    _relief?.dispose();
    super.dispose();
  }

  Future<void> _build() async {
    final gen = ++_generation;
    try {
      final image = await _renderRelief(widget.dem, widget.lat, widget.lon, widget.span,
          widget.resolution);
      if (!mounted || gen != _generation) {
        image.dispose();
        return;
      }
      setState(() {
        _relief?.dispose();
        _relief = image;
      });
    } catch (_) {
      // The same rule the rest of this app follows: a surface that cannot be drawn says so rather
      // than showing an empty box that reads as a styling choice.
      if (mounted && gen == _generation) setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) {
      return _frame(
        Center(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              widget.failureText,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
            ),
          ),
        ),
      );
    }

    final relief = _relief;
    if (relief == null) {
      // Static, deliberately. A CircularProgressIndicator animates forever, so any test that calls
      // pumpAndSettle while the relief is building hangs until it times out - and the same spinner
      // would cost a frame every 16ms on the phone for a state that lasts a few milliseconds.
      return _frame(Center(
        child: Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFF1E3A5F), width: 2),
            borderRadius: BorderRadius.circular(11),
          ),
        ),
      ));
    }

    return _frame(ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: CustomPaint(
        painter: _OverlayPainter(
          relief: relief,
          dem: widget.dem,
          lat: widget.lat,
          lon: widget.lon,
          span: widget.span,
          marks: widget.marks,
          route: widget.route,
        ),
        size: Size.infinite,
      ),
    ));
  }

  Widget _frame(Widget child) => Container(
        decoration: BoxDecoration(
          color: const Color(0xFF070B14),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        height: 240,
        width: double.infinity,
        child: child,
      );
}

/// Compute the shaded relief once and hand it back as a GPU-uploadable image.
Future<ui.Image> _renderRelief(
    Dem dem, double centreLat, double centreLon, double span, int resolution) async {
  final spanLat = span;
  final spanLon = span / math.max(0.2, math.cos(centreLat * math.pi / 180.0));
  final north = centreLat + spanLat / 2;
  final south = centreLat - spanLat / 2;
  final west = centreLon - spanLon / 2;
  final east = centreLon + spanLon / 2;

  final w = resolution;
  final h = resolution;
  final px = Uint8List(w * h * 4);

  final dLat = (north - south) / h;
  final dLon = (east - west) / w;

  // The window's own range, so the ramp is stretched over the ground actually on screen.
  //
  // Keyed to absolute height this map is camouflage: a window around Melamchi spans a few hundred
  // metres of relief, the 0-8461 m ramp gives it two or three colours, and the result reads as flat
  // patches. Stretching the same ramp over the local min and max is the difference between a height
  // key and a picture of terrain.
  var lo = double.infinity, hi = -double.infinity;
  for (var r = 0; r < h; r += 4) {
    final la = north - (r + 0.5) * dLat;
    for (var c = 0; c < w; c += 4) {
      final v = _sample(dem, la, west + (c + 0.5) * dLon);
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  if (!lo.isFinite || !hi.isFinite) {
    lo = 0;
    hi = 1;
  }
  // A floor on the range stops a dead-flat window from amplifying rounding noise into mountains.
  if (hi - lo < 150) hi = lo + 150;

  // Metres per cell, used to keep the light angle honest at this latitude: a degree of longitude is
  // shorter than a degree of latitude, and without this the terrain looks stretched east-west.
  final cellM = dLat * 111320.0;
  final metresPerLon = 111320.0 * math.cos(centreLat * math.pi / 180.0);

  // North-west light, the cartographic convention. Azimuth 315 degrees, altitude 45.
  const az = 315.0 * math.pi / 180.0;
  const alt = 45.0 * math.pi / 180.0;
  final lx = math.cos(alt) * math.sin(az);
  final ly = math.cos(alt) * math.cos(az);
  final lz = math.sin(alt);

  for (var r = 0; r < h; r++) {
    final lat = north - (r + 0.5) * dLat;
    for (var c = 0; c < w; c++) {
      final lon = west + (c + 0.5) * dLon;

      final centre = _sample(dem, lat, lon);
      // The gradient must be taken across a real DEM cell, not across an output pixel: at 0.35 degrees
      // of window the output step is ten times finer than the grid, so a pixel-spaced difference falls
      // inside one cell and returns zero. That is the whole difference between terrain and flat blocks.
      final gl = dem.pixelDegLon, ga = dem.pixelDegLat;
      final e = _sample(dem, lat, lon + gl);
      final wst = _sample(dem, lat, lon - gl);
      final n = _sample(dem, lat + ga, lon);
      final s = _sample(dem, lat - ga, lon);

      final dzdx = (e - wst) / (2 * gl * metresPerLon);
      final dzdy = (n - s) / (2 * ga * cellM);

      // Surface normal, normalised.
      var nx = -dzdx, ny = -dzdy, nz = 1.0;
      final len = math.sqrt(nx * nx + ny * ny + nz * nz);
      nx /= len;
      ny /= len;
      nz /= len;

      var shade = nx * lx + ny * ly + nz * lz;
      if (shade < 0) shade = 0;
      // Lift the ambient so valleys read as land rather than as holes.
      shade = 0.25 + 0.75 * shade;

      final rgb = _hypsometric(centre, lo, hi);
      final i = (r * w + c) * 4;
      // Slight gamma so the low Terai does not flatten into one dark band.
      final k = math.pow(shade, 0.85).toDouble();
      px[i] = (rgb[0] * k).clamp(0, 255).toInt();
      px[i + 1] = (rgb[1] * k).clamp(0, 255).toInt();
      px[i + 2] = (rgb[2] * k).clamp(0, 255).toInt();
      px[i + 3] = 255;
    }
  }

  final completer = Completer<ui.Image>();
  ui.decodeImageFromPixels(px, w, h, ui.PixelFormat.rgba8888, completer.complete);
  return completer.future;
}

/// Elevation with bilinear interpolation, in metres.
///
/// Nearest-cell sampling was the first bug in this widget and it was visible immediately: the national
/// grid is about 0.011 degrees per cell, so a 0.35-degree window holds roughly 32 cells. Drawing that
/// into 320 pixels at nearest-neighbour does not show terrain, it shows the data grid - and the
/// gradient computed between two samples that landed in the same cell is zero, which is why the first
/// render was flat blocks outlined in black.
double _sample(Dem dem, double lat, double lon) {
  final fx = (lon - dem.west) / dem.pixelDegLon;
  final fy = (dem.north - lat) / dem.pixelDegLat;
  final x0 = fx.floor(), y0 = fy.floor();
  final tx = fx - x0, ty = fy - y0;
  double at(int x, int y) {
    final cx = x.clamp(0, dem.cols - 1);
    final cy = y.clamp(0, dem.rows - 1);
    return dem.elevation[cy * dem.cols + cx].toDouble();
  }
  final a = at(x0, y0), b = at(x0 + 1, y0), c = at(x0, y0 + 1), d = at(x0 + 1, y0 + 1);
  return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
}

/// Height to colour: green Terai, ochre middle hills, grey rock, white snow.
///
/// Deliberately a banded ramp rather than a smooth gradient. Bands read as elevation on a small
/// phone screen where a continuous ramp just looks like haze, and they survive being scaled down.
List<int> _hypsometric(double metres, double lo, double hi) {
  // Re-key the ramp to the window, then read it as before.
  metres = 8461 * (metres - lo) / (hi - lo);
  const stops = <List<int>>[
    [0, 0x2E, 0x5A, 0x33], // lowland green
    [500, 0x4A, 0x6B, 0x2F],
    [1200, 0x77, 0x7B, 0x3A],
    [2000, 0x9C, 0x86, 0x4A], // ochre hills
    [3000, 0xB2, 0x9A, 0x6E],
    [4000, 0xA8, 0xA0, 0x9A], // rock
    [5000, 0xC9, 0xC6, 0xC2],
    [5800, 0xF2, 0xF4, 0xF6], // snow
    [8461, 0xFF, 0xFF, 0xFF],
  ];
  if (metres <= stops.first[0]) return stops.first.sublist(1);
  for (var i = 1; i < stops.length; i++) {
    if (metres <= stops[i][0]) {
      final a = stops[i - 1], b = stops[i];
      final t = (metres - a[0]) / (b[0] - a[0]);
      return [
        (a[1] + (b[1] - a[1]) * t).round(),
        (a[2] + (b[2] - a[2]) * t).round(),
        (a[3] + (b[3] - a[3]) * t).round(),
      ];
    }
  }
  return stops.last.sublist(1);
}

class _OverlayPainter extends CustomPainter {
  final ui.Image relief;
  final Dem dem;
  final double lat;
  final double lon;
  final double span;
  final List<MapMark> marks;
  final List<List<double>>? route;

  _OverlayPainter({
    required this.relief,
    required this.dem,
    required this.lat,
    required this.lon,
    required this.span,
    required this.marks,
    required this.route,
  });

  /// Degrees -> normalised position in the window, x right and y down.
  Offset _project(double pLat, double pLon, Size size) {
    final spanLon = span / math.max(0.2, math.cos(lat * math.pi / 180.0));
    final north = lat + span / 2, west = lon - spanLon / 2;
    final fx = (pLon - west) / spanLon;
    final fy = (north - pLat) / span;
    return Offset(fx * size.width, fy * size.height);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final src = Rect.fromLTWH(0, 0, relief.width.toDouble(), relief.height.toDouble());
    canvas.drawImageRect(relief, src, Offset.zero & size, Paint()..filterQuality = FilterQuality.medium);

    // A faint graticule so the window reads as a map rather than a picture.
    final grid = Paint()
      ..color = const Color(0x1AFFFFFF)
      ..strokeWidth = 0.6;
    for (var i = 1; i < 4; i++) {
      final x = size.width * i / 4;
      final y = size.height * i / 4;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    // The route first, so markers sit on top of it.
    final r = route;
    if (r != null && r.length > 1) {
      final path = Path();
      for (var i = 0; i < r.length; i++) {
        final p = _project(r[i][0], r[i][1], size);
        i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = const Color(0xFF0B1220)
          ..strokeWidth = 5
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round,
      );
      canvas.drawPath(
        path,
        Paint()
          ..color = const Color(0xFF38BDF8)
          ..strokeWidth = 2.4
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round,
      );
    }

    for (final m in marks) {
      final p = _project(m.lat, m.lon, size);
      if (p.dx < -20 || p.dy < -20 || p.dx > size.width + 20 || p.dy > size.height + 20) continue;

      final colour = switch (m.kind) {
        MapMarkKind.you => const Color(0xFF38BDF8),
        MapMarkKind.slope => const Color(0xFFF87171),
        MapMarkKind.destination => const Color(0xFF4ADE80),
        MapMarkKind.place => const Color(0xFFE2E8F0),
      };

      if (m.kind == MapMarkKind.you) {
        // A ring, because "you are here" should not look like a pin someone dropped.
        canvas.drawCircle(p, 9, Paint()..color = colour.withValues(alpha: 0.22));
        canvas.drawCircle(
            p, 9, Paint()..color = colour..style = PaintingStyle.stroke..strokeWidth = 2);
        canvas.drawCircle(p, 3.5, Paint()..color = colour);
      } else {
        canvas.drawCircle(p, 7, Paint()..color = const Color(0xCC0B1220));
        canvas.drawCircle(p, 4.5, Paint()..color = colour);
        canvas.drawCircle(
            p, 4.5, Paint()..color = const Color(0x66FFFFFF)..style = PaintingStyle.stroke..strokeWidth = 1);
      }

      if (m.label.isNotEmpty) {
        final tp = TextPainter(
          text: TextSpan(
            text: m.label,
            style: const TextStyle(
              color: Color(0xFFF1F5F9),
              fontSize: 9.5,
              fontWeight: FontWeight.w600,
              shadows: [Shadow(color: Color(0xFF000000), blurRadius: 3)],
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout(maxWidth: size.width * 0.7);
        var dx = p.dx + 10;
        if (dx + tp.width > size.width - 4) dx = p.dx - 10 - tp.width;
        var dy = p.dy - tp.height / 2;
        dy = dy.clamp(2.0, size.height - tp.height - 2);
        tp.paint(canvas, Offset(dx, dy));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _OverlayPainter old) =>
      old.relief != relief ||
      old.lat != lat ||
      old.lon != lon ||
      old.span != span ||
      old.marks != marks ||
      old.route != route;
}
