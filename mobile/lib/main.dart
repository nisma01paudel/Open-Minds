/// Pahiro — the field app, on Flutter, working with no network at all.
///
/// The order of the first two screens is deliberate and is the point of this file:
///
///   1. **Choose a language**, before anything else, shown in both languages at once, because
///      the person who most needs this app may not read Nepali and the person who lives here
///      may not want English. Everything after this is in their choice, and it is remembered.
///   2. **भाग्नुहोस् / Escape** — which way to run, and how high, computed on the phone from the
///      bundled elevation grid with the network already gone.
///
/// Platform capabilities that need plugins (geolocation, text-to-speech, BLE advertising) are
/// reached through the interfaces below rather than called directly, so the screens can be tested
/// headlessly and so it is visible which parts a test has actually exercised. None of them is
/// load-bearing: the escape direction, the beacon frame and the language all work without any.
library;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

import 'beacon.dart' as beacon;
import 'escape.dart' as escape;
import 'l10n.dart';
import 'offline_ai.dart' as ai;
import 'trails.dart';

/// Speech, behind an interface so tests do not need a platform channel.
abstract class Speaker {
  Future<bool> speak(String text, String langCode);
}

/// Does nothing, successfully. The default in tests, and on a device with no speech engine.
class SilentSpeaker implements Speaker {
  const SilentSpeaker();
  @override
  Future<bool> speak(String text, String langCode) async => false;
}

/// The real one.
///
/// It returns false deliberately: `flutter_tts` is not a dependency of this build, and adding a
/// plugin whose behaviour no test in this repository exercises would be a *claim*, not a
/// capability. The interface exists so the screen is written against it and the wiring is one
/// line when the plugin is added. The Nepali voice itself is Piper `ne_NP`, 63 MB, MIT, which
/// runs on the handset with no network - see docs/MODELS.md.
class PlatformSpeaker implements Speaker {
  const PlatformSpeaker();

  @override
  Future<bool> speak(String text, String langCode) async => false;
}

/// Where a place is. A short list of real Nepali towns, each one a place where this question has
/// had to be answered for real.
class Place {
  final String nameEn;
  final String nameNe;
  final double lat;
  final double lon;
  final String why;
  const Place(this.nameEn, this.nameNe, this.lat, this.lon, this.why);
}

const List<Place> places = [
  Place('Melamchi', 'मेलम्ची', 27.8300, 85.5700,
      'the bazaar the 2021 flash flood destroyed'),
  Place('Beni, Myagdi', 'बेनी, म्याग्दी', 28.3500, 83.5700, 'Kali Gandaki valley'),
  Place('Barhabise', 'बाह्रबिसे', 27.7900, 85.8900, 'Bhote Koshi gorge'),
  Place('Pokhara', 'पोखरा', 28.2096, 83.9856, 'Seti gorge'),
  Place('Kathmandu', 'काठमाडौं', 27.7172, 85.3240, 'Bagmati valley'),
  Place('Nepalgunj', 'नेपालगन्ज', 28.0500, 81.6167, 'the Terai, where nothing is near'),
];

void main() {
  runApp(PahiroApp(controller: LanguageController(), speaker: const PlatformSpeaker()));
}

class PahiroApp extends StatelessWidget {
  final LanguageController controller;
  final Speaker speaker;
  final DemLoader demLoader;

  PahiroApp({
    super.key,
    required this.controller,
    required this.speaker,
    DemLoader? demLoader,
  }) : demLoader = demLoader ?? AssetDemLoader();

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<AppLang?>(
      valueListenable: controller,
      builder: (context, lang, _) => MaterialApp(
        title: 'Pahiro',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF38BDF8),
            brightness: Brightness.dark,
          ),
          scaffoldBackgroundColor: const Color(0xFF070B14),
        ),
        home: lang == null
            ? LanguageGate(controller: controller)
            : HomeShell(
                controller: controller,
                speaker: speaker,
                demLoader: demLoader,
              ),
      ),
    );
  }
}

/// The first screen anyone sees. Both languages at once, because the choice has to be readable by
/// someone who has not yet told us which language they read.
class LanguageGate extends StatelessWidget {
  final LanguageController controller;
  const LanguageGate({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('पहिरो · Pahiro',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  Text(L10n.both('app.tagline'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Color(0xFF94A3B8), height: 1.6)),
                  const SizedBox(height: 32),
                  Text(L10n.both('lang.choose'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 18),
                  for (final lang in AppLang.values)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: FilledButton(
                        onPressed: () => controller.choose(lang),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 20),
                        ),
                        child: Text(
                          '${lang.endonym}   ·   ${lang.englishName}',
                          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                  const SizedBox(height: 6),
                  Text(L10n.both('lang.chooseHint'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: Color(0xFF64748B), fontSize: 12, height: 1.5)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Loads the elevation grid. Behind an interface so a widget test can supply a small synthetic one
/// instead of the 852 KB national asset.
abstract class DemLoader {
  Future<escape.Dem?> load();
}

class AssetDemLoader implements DemLoader {
  @override
  Future<escape.Dem?> load() async {
    try {
      final bin = await rootBundle.load('assets/terrain.bin');
      final meta = await rootBundle.loadString('assets/terrain.json');
      return escape.Dem.fromBytes(
        bin.buffer.asUint8List(bin.offsetInBytes, bin.lengthInBytes),
        meta,
      );
    } catch (_) {
      // A missing asset must not take the rest of the app down with it.
      return null;
    }
  }
}

class HomeShell extends StatefulWidget {
  final LanguageController controller;
  final Speaker speaker;
  final DemLoader demLoader;
  final TrailLoader trailLoader;
  const HomeShell({
    super.key,
    required this.controller,
    required this.speaker,
    required this.demLoader,
    this.trailLoader = const AssetTrailLoader(),
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<AppLang?>(
      valueListenable: widget.controller,
      builder: (context, lang, _) {
        final s = widget.controller.strings;
        return Scaffold(
          appBar: AppBar(
            title: Text('${s['app.title']} · ${s['app.tagline']}', maxLines: 1,
                overflow: TextOverflow.ellipsis),
            titleTextStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          body: IndexedStack(
            index: index,
            children: [
              EscapeScreen(
                  strings: s,
                  lang: lang ?? AppLang.en,
                  speaker: widget.speaker,
                  demLoader: widget.demLoader),
              WalkScreen(strings: s, lang: lang ?? AppLang.en, loader: widget.trailLoader),
              BeaconScreen(strings: s),
              BoardScreen(strings: s),
              SettingsScreen(strings: s, controller: widget.controller),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: index,
            onDestinationSelected: (i) => setState(() => index = i),
            destinations: [
              NavigationDestination(
                  icon: const Icon(Icons.trending_up), label: s['tab.escape']),
              NavigationDestination(
                  icon: const Icon(Icons.hiking), label: s['tab.walk']),
              NavigationDestination(
                  icon: const Icon(Icons.bluetooth_searching), label: s['tab.beacon']),
              NavigationDestination(icon: const Icon(Icons.list_alt), label: s['tab.board']),
              NavigationDestination(icon: const Icon(Icons.settings), label: s['tab.settings']),
            ],
          ),
        );
      },
    );
  }
}

/// Loads the trail bundle. Injected so a test does not need a real asset bundle, the same way
/// [DemLoader] works for the terrain grid.
abstract class TrailLoader {
  Future<TrailNetwork> load();
}

class AssetTrailLoader implements TrailLoader {
  const AssetTrailLoader();
  @override
  Future<TrailNetwork> load() async =>
      TrailNetwork.fromBytes(await rootBundle.load('assets/trails.geojson')
          .then((b) => b.buffer.asUint8List()));
}

/// पदयात्रा — which walk can I do from here, with no network.
///
/// This is the ordinary-day half of the app. It reads the same trail bundle the web app serves,
/// and it answers the question a person standing at a trailhead asks. It does not do
/// point-to-point routing: that lives in the Python engine, and a second graph router in a second
/// language is how two implementations quietly stop agreeing.
class WalkScreen extends StatefulWidget {
  final L10n strings;
  final AppLang lang;
  final TrailLoader loader;
  const WalkScreen({super.key, required this.strings,
                    required this.lang, required this.loader});

  @override
  State<WalkScreen> createState() => _WalkScreenState();
}

class _WalkScreenState extends State<WalkScreen> {
  TrailNetwork? _net;
  String? _error;
  bool _busy = true;
  // Kathmandu, until the phone reports a fix. Stated in the UI rather than assumed silently.
  double _lat = 27.7047, _lon = 85.3146;
  double _radiusM = 3000;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _busy = true; _error = null; });
    try {
      final net = await widget.loader.load();
      if (mounted) setState(() { _net = net; _busy = false; });
    } catch (e) {
      if (mounted) setState(() { _error = '$e'; _busy = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    if (_busy) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24),
        child: Text('${s['walk.loadfail']}\n$_error', textAlign: TextAlign.center)));
    }
    final net = _net!;
    final got = net.nearby(_lon, _lat, radiusM: _radiusM, limit: 20);

    return ListView(padding: const EdgeInsets.all(16), children: [
      Text(s['walk.title'], style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 4),
      Text('${s['walk.from']} ${_lat.toStringAsFixed(4)}, ${_lon.toStringAsFixed(4)}',
           style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 12),
      Row(children: [
        Text('${s['walk.within']} '),
        Expanded(child: Slider(
          value: _radiusM, min: 500, max: 8000, divisions: 15,
          label: '${(_radiusM / 1000).toStringAsFixed(1)} km',
          onChanged: (v) => setState(() => _radiusM = v),
        )),
        Text('${(_radiusM / 1000).toStringAsFixed(1)} km'),
      ]),
      if (got.isEmpty)
        Padding(padding: const EdgeInsets.symmetric(vertical: 24),
          child: Text(s['walk.none'], style: Theme.of(context).textTheme.bodyMedium)),
      for (final t in got) Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: ListTile(
          leading: const Icon(Icons.hiking),
          title: Text(t.label),
          subtitle: Text('${(t.lengthM / 1000).toStringAsFixed(1)} km · '
              '${t.difficulty} · ${t.flatMinutes} min'),
          trailing: Text('${t.nearestM.round()} m'),
          onTap: () => setState(() { _lat = t.points.first[1]; _lon = t.points.first[0]; }),
        ),
      ),
      const SizedBox(height: 12),
      Text(s['walk.caveat'], style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 8),
      Text(net.attribution, style: Theme.of(context).textTheme.bodySmall),
    ]);
  }
}

/// भाग्नुहोस् — which way to run, and how high. Computed on the phone.
class EscapeScreen extends StatefulWidget {
  final L10n strings;
  final AppLang lang;
  final Speaker speaker;
  final DemLoader demLoader;
  const EscapeScreen({
    super.key,
    required this.strings,
    required this.lang,
    required this.speaker,
    required this.demLoader,
  });

  @override
  State<EscapeScreen> createState() => _EscapeScreenState();
}

class _EscapeScreenState extends State<EscapeScreen> {
  escape.Dem? dem;
  bool loading = true;
  Place place = places.first;
  double rise = escape.defaultRiseM;
  escape.Escape? plan;
  String? note;

  @override
  void initState() {
    super.initState();
    widget.demLoader.load().then((d) {
      if (!mounted) return;
      setState(() {
        dem = d;
        loading = false;
      });
    });
  }

  void _plan() {
    final d = dem;
    if (d == null) {
      setState(() => note = widget.strings['escape.notLoaded']);
      return;
    }
    final e = escape.planEscape(d, place.lat, place.lon, riseM: rise);
    setState(() {
      plan = e;
      note = null;
    });
    // Speak the first instruction immediately: the person using this has both hands full.
    widget.speaker.speak(escape.steps(e).first.spoken(lang: widget.lang.code),
        widget.lang.code);
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(s['escape.title'],
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text(s['escape.blurb'],
            style: const TextStyle(color: Color(0xFF94A3B8), height: 1.5)),
        const SizedBox(height: 8),
        Text(s['escape.offline'],
            style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 12)),
        const SizedBox(height: 18),
        Text(s['escape.place'], style: const TextStyle(fontWeight: FontWeight.w600)),
        DropdownButtonFormField<Place>(
          initialValue: place,
          items: [
            for (final p in places)
              DropdownMenuItem(
                value: p,
                child: Text(widget.lang == AppLang.ne ? '${p.nameNe} · ${p.nameEn}' : p.nameEn),
              ),
          ],
          onChanged: (p) => setState(() => place = p ?? place),
        ),
        const SizedBox(height: 14),
        Text('${s['escape.rise']} · ${rise.toStringAsFixed(0)} m',
            style: const TextStyle(fontWeight: FontWeight.w600)),
        Slider(
          value: rise,
          min: 1,
          max: 40,
          divisions: 39,
          label: '${rise.toStringAsFixed(0)} m',
          onChanged: (v) => setState(() => rise = v),
        ),
        const SizedBox(height: 6),
        FilledButton(
          onPressed: loading ? null : _plan,
          style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 18)),
          child: Text(s['escape.go'], style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
        const SizedBox(height: 18),
        if (loading) const Center(child: CircularProgressIndicator()),
        if (note != null) Text(note!, style: const TextStyle(color: Color(0xFFF59E0B))),
        if (plan != null)
          EscapeResult(
              plan: plan!, strings: s, lang: widget.lang, speaker: widget.speaker),
      ],
    );
  }
}

class EscapeResult extends StatelessWidget {
  final escape.Escape plan;
  final L10n strings;
  final AppLang lang;
  final Speaker speaker;
  const EscapeResult({
    super.key,
    required this.plan,
    required this.strings,
    required this.lang,
    required this.speaker,
  });

  @override
  Widget build(BuildContext context) {
    final e = plan;
    final heading = e.reachable
        ? '${(e.compassName ?? '').toUpperCase()} · ${e.distanceM!.toStringAsFixed(0)} m'
            '${e.climbM != null && e.climbM! > 1 ? ' · +${e.climbM!.toStringAsFixed(0)} m' : ''}'
        : strings['escape.noGround'];

    final planSteps = escape.steps(e);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              heading,
              style: TextStyle(
                fontSize: 23,
                fontWeight: FontWeight.w700,
                color: e.reachable ? const Color(0xFFE0F2FE) : const Color(0xFFFFB4A2),
              ),
            ),
            const SizedBox(height: 8),
            if (e.reachable)
              Text(
                '${e.fromElevationM.toStringAsFixed(0)} m → '
                '${e.targetElevationM!.toStringAsFixed(0)} m · '
                '~${e.walkMinutes!.toStringAsFixed(0)} min',
                style: const TextStyle(color: Color(0xFF94A3B8)),
              ),
            const SizedBox(height: 12),
            Text(escape.adviceNe(e), style: const TextStyle(fontSize: 16, height: 1.6)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  onPressed: () => speaker.speak(planSteps.first.ne, 'ne'),
                  child: Text(strings['escape.speak']),
                ),
                if (e.reachable && planSteps.length > 1)
                  OutlinedButton(
                    onPressed: () => speaker.speak(planSteps[1].ne, 'ne'),
                    child: Text(strings['escape.directionOnly']),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            for (final st in planSteps)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(st.ne, style: const TextStyle(fontWeight: FontWeight.w600)),
                    Text(st.en,
                        style: const TextStyle(color: Color(0xFF64748B), fontSize: 12)),
                  ],
                ),
              ),
            const Divider(height: 26),
            Text(escape.terrainCaveat,
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 11, height: 1.5)),
          ],
        ),
      ),
    );
  }
}

/// Beacon — a message that needs no connection.
class BeaconScreen extends StatefulWidget {
  final L10n strings;
  const BeaconScreen({super.key, required this.strings});

  @override
  State<BeaconScreen> createState() => _BeaconScreenState();
}

class _BeaconScreenState extends State<BeaconScreen> {
  Uint8List? frame;
  beacon.Beacon? decoded;

  void _build() {
    final f = beacon.encode(
      'handset-demo',
      'msg-${DateTime.now().millisecondsSinceEpoch}',
      kind: 'sos',
      lat: 27.71542,
      lon: 85.31234,
      people: 2,
      severity: 'critical',
      lowBattery: true,
    );
    setState(() {
      frame = f;
      decoded = beacon.decode(beacon.relay(f));
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(s['beacon.title'],
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text(s['beacon.blurb'],
            style: const TextStyle(color: Color(0xFF94A3B8), height: 1.5)),
        const SizedBox(height: 16),
        FilledButton(onPressed: _build, child: Text(s['beacon.encode'])),
        const SizedBox(height: 16),
        if (frame != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${frame!.length} ${s['beacon.bytes']} · '
                    '${beacon.maxAdBytes - frame!.length} spare of ${beacon.maxAdBytes}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  SelectableText(beacon.hexOf(frame!),
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                  const SizedBox(height: 10),
                  if (decoded != null) ...[
                    Text('${decoded!.peopleText} · ${decoded!.severity}'),
                    Text(decoded!.hasPosition
                        ? 'position ${decoded!.lat!.toStringAsFixed(5)}, '
                            '${decoded!.lon!.toStringAsFixed(5)}'
                        : 'no position fix'),
                    Text('ttl ${decoded!.ttl} · hops ${decoded!.hops} (relayed once)'),
                  ],
                  const SizedBox(height: 10),
                  const Text('A Flutter app can put bytes on the air. A browser cannot.',
                      style: TextStyle(color: Color(0xFF38BDF8), fontSize: 12)),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class BoardScreen extends StatelessWidget {
  final L10n strings;
  const BoardScreen({super.key, required this.strings});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(strings['board.empty'],
            style: const TextStyle(color: Color(0xFF64748B)),
            textAlign: TextAlign.center),
      ),
    );
  }
}

class SettingsScreen extends StatelessWidget {
  final L10n strings;
  final LanguageController controller;
  const SettingsScreen({super.key, required this.strings, required this.controller});

  @override
  Widget build(BuildContext context) {
    final f = ai.fit();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(strings['settings.title'],
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 18),
        Text(strings['settings.language'], style: const TextStyle(fontWeight: FontWeight.w600)),
        RadioGroup<AppLang>(
          groupValue: controller.value,
          onChanged: (v) => controller.choose(v ?? AppLang.en),
          child: Column(
            children: [
              for (final lang in AppLang.values)
                RadioListTile<AppLang>(
                  value: lang,
                  title: Text('${lang.endonym}  ·  ${lang.englishName}'),
                ),
            ],
          ),
        ),
        const Divider(height: 32),
        Text(strings['settings.model'], style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${f.tier.name} — ${f.tier.note}', style: const TextStyle(height: 1.5)),
                const SizedBox(height: 8),
                Text(
                  'needs ~${f.tier.ramMb.toStringAsFixed(0)} MB resident, '
                  '${f.tier.weightsMb.toStringAsFixed(0)} MB on disk',
                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
                if (f.tier.weightsMb == 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(strings['settings.noModel'],
                        style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 12)),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
