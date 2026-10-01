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
import 'package:flutter_tts/flutter_tts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:share_plus/share_plus.dart';
import 'package:flutter_ble_peripheral/flutter_ble_peripheral.dart';
import 'package:flutter/services.dart' show rootBundle;

import 'beacon.dart' as beacon;
import 'dart:convert';

import 'duty.dart';
import 'places.dart';
import 'seasons.dart' as seasons;
import 'escape.dart' as escape;
import 'terrainmap.dart';
import 'theme.dart';
import 'vr.dart';
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
/// The platform speaker.
///
/// **It returns false and always has.** There is no text-to-speech implementation behind it - no
/// flutter_tts, no platform channel - so every button wired to it is a control that renders, is
/// pressed, and does nothing. On the escape screen that button says "speak" to somebody standing in
/// the rain with both hands full.
///
/// The honest thing is not to pretend: the callers now show the false, and this docstring says why
/// rather than leaving a stub labelled "the real one". Wiring an engine is a dependency and a device
/// test, so it is named here as work rather than implied as done.
class PlatformSpeaker implements Speaker {
  const PlatformSpeaker();

  /// One engine for the process: constructing FlutterTts per utterance leaks a platform channel
  /// each time, and this is called from a button a frightened person may press repeatedly.
  static final FlutterTts _tts = FlutterTts();

  /// `Ne` is what the app passes; Android wants a full tag. Kept here rather than at the call sites
  /// because the mapping is a property of the engine, not of the screen.
  static const _tags = {'ne': 'ne-NP', 'en': 'en-US'};

  @override
  Future<bool> speak(String text, String langCode) async {
    final tag = _tags[langCode] ?? langCode;
    try {
      // The false is the whole point. Android does not ship a Nepali voice on every device, and a
      // silent button is worse than an honest one: the caller shows this failure.
      final available = await _tts.isLanguageAvailable(tag);
      if (available != true) return false;
      await _tts.setLanguage(tag);
      await _tts.speak(text);
      return true;
    } catch (_) {
      // No engine, no permission, a platform channel that is not there - all the same to the caller.
      return false;
    }
  }
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

/// The place a person picked last time.
///
/// The escape screen opened on Melamchi for everybody, including people standing in Pokhara. The
/// language already survives a restart; the second thing worth keeping is where the user actually is,
/// because re-picking it is a tap in the moment they have least attention to spare.
const _placePrefsKey = 'pahiro.place';

Future<String?> _rememberedPlace() async {
  try {
    return (await SharedPreferences.getInstance()).getString(_placePrefsKey);
  } catch (_) {
    return null;      // no store, no memory - the default is simply used again
  }
}

void _rememberPlace(Place p) {
  // Fire and forget, for the same reason the language choice is: a dropdown should not wait on a disk.
  SharedPreferences.getInstance()
      .then((s) => s.setString(_placePrefsKey, p.nameEn))
      .catchError((_) => false);   // returns bool: setString does, and nothing reads it
}

void main() {
  // SharedPreferences needs a binding before the first frame can ask it anything.
  WidgetsFlutterBinding.ensureInitialized();
  final controller = LanguageController();
  runApp(PahiroApp(controller: controller, speaker: const PlatformSpeaker()));

  // Restore AFTER the first frame rather than before it. Awaiting the preference store here would
  // hold a blank screen in front of somebody who may be opening this in a hurry, to save them one
  // tap. And it is guarded by !chosen so a restore can never overwrite a choice already made.
  LanguageController.remembered().then((saved) {
    if (saved != null && !controller.chosen) controller.value = saved;
  });
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
        theme: PahiroTheme.light(),
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
                      style: const TextStyle(color: PahiroTheme.inkMuted, height: 1.6)),
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
                          color: PahiroTheme.inkMuted, fontSize: 12, height: 1.5)),
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
            titleTextStyle: const TextStyle(
                fontSize: 15, fontWeight: FontWeight.w700, color: PahiroTheme.ink),
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

abstract class SeasonLoader {
  Future<seasons.SeasonGuide> load();
}

class AssetSeasonLoader implements SeasonLoader {
  const AssetSeasonLoader();
  @override
  Future<seasons.SeasonGuide> load() async =>
      seasons.SeasonGuide.parse(await rootBundle.loadString('assets/seasons.json'));
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

  /// When to go. Defaulted rather than required so every existing caller keeps working: the season
  /// guide is additional information, not a precondition for finding a walk.
  final SeasonLoader seasonLoader;
  const WalkScreen({super.key, required this.strings,
                    required this.lang, required this.loader,
                    this.seasonLoader = const AssetSeasonLoader()});

  @override
  State<WalkScreen> createState() => _WalkScreenState();
}

class _WalkScreenState extends State<WalkScreen> {
  TrailNetwork? _net;
  seasons.SeasonGuide? _seasons;
  bool _seasonsFailed = false;
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
      // The walk list is shown the moment the trails are ready. The season guide is loaded AFTER,
      // and a failure is deliberately not fatal - but more importantly it must never hold the
      // screen: awaiting it here left _busy true forever when the asset did not resolve, and
      // sixteen widget tests failed on pumpAndSettle timing out behind a spinner that would not
      // stop. A twelve-month guide is not a precondition for finding a walk this afternoon.
      if (mounted) setState(() { _net = net; _busy = false; });
      try {
        final sg = await widget.seasonLoader.load();
        if (mounted) setState(() { _seasons = sg; });
      } catch (_) {
        // The walk list is what matters here, so a failed season load must not block it - but it
        // must not VANISH either. The same defect I fixed in the three panels was still here: a
        // strip that fails to load and a strip with nothing to say looked identical.
        if (mounted) setState(() => _seasonsFailed = true);
      }
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
      if (_seasonsFailed) loadFailed(s['load.failed']),
      if (_seasons != null) seasonStrip(s, _seasons!, _lat, _lon),
      const SizedBox(height: 14),
      PlacesPanel(
        title: s['places.title'], caption: s['places.caption'],
        slopesLabel: s['places.slopes'], trailsLabel: s['places.trails'],
        nepali: s.lang == AppLang.ne, lat: _lat, lon: _lon, failedLabel: s['load.failed'],
        siteNote: s['duty.unencrypted'],
      ),
      if (_seasons != null) ...[
        const SizedBox(height: 14),
        PanoramaView(
          regionKey: _seasons!.nearest(_lat, _lon)?.key ?? 'kathmandu',
          title: s['walk.look'],
          caption: s['walk.lookNote'],
          fallback: s['walk.noPanorama'],
          vrLabel: s['walk.vr'],
          onVr: () => Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => VrPanorama(
              asset: 'assets/panoramas/${_seasons!.nearest(_lat, _lon)?.key ?? 'kathmandu'}.png',
              title: s['walk.look'],
              hint: s['walk.noPanorama'],
              monoscopicNote: s['vr.monoscopic'],
              recenter: s['vr.recenter'],
              noGyro: s['vr.noGyro'],
              close: s['vr.close'],
            ),
          )),
        ),
      ],
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
    // Guarded so a restore cannot overwrite a choice made while it was in flight.
    _rememberedPlace().then((name) {
      if (name == null || !mounted || place != places.first) return;
      for (final p in places) {
        if (p.nameEn == name) {
          setState(() => place = p);
          return;
        }
      }
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
        DemoPanel(
          title: s['demo.title'], blurb: s['demo.blurb'], runLabel: s['demo.run'],
          nextLabel: s['demo.next'], liveLabel: s['demo.live'], citedLabel: s['demo.cited'],
          nepali: s.lang == AppLang.ne, failedLabel: s['load.failed'],
        ),
        const SizedBox(height: 12),
        DutyPanel(
          strings: s.lang.code, lat: place.lat, lon: place.lon,
          unencrypted: s['duty.unencrypted'],
          title: s['duty.title'], caption: s['duty.where'],
          noAddress: s['duty.noAddress'], defaultNote: s['duty.default'],
          draftButton: s['duty.draft'], letterNote: s['duty.letterNote'],
          nepali: s.lang == AppLang.ne, failedLabel: s['load.failed'],
        ),
        const SizedBox(height: 12),
        Text(s['escape.title'],
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text(s['escape.blurb'],
            style: const TextStyle(color: PahiroTheme.inkMuted, height: 1.5)),
        const SizedBox(height: 8),
        Text(s['escape.offline'],
            style: const TextStyle(color: PahiroTheme.primary, fontSize: 12)),
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
          onChanged: (p) {
                    final chosen = p ?? place;
                    setState(() => place = chosen);
                    _rememberPlace(chosen);
                  },
        ),
        const SizedBox(height: 14),
        // A map, because "which way, and how high" is a question about ground, and until now the
        // app answered it with a sentence. The relief is drawn on the phone from the elevation grid
        // that already ships with it - no tiles, no network, nothing new to download.
        if (dem != null)
          TerrainMap(
            dem: dem!,
            lat: place.lat,
            lon: place.lon,
            span: 0.35,
            failureText: s['escape.mapFailed'],
            marks: [
              MapMark(place.lat, place.lon, s['escape.you'],
                  kind: MapMarkKind.you),
              if (plan?.targetLat != null)
                MapMark(plan!.targetLat!, plan!.targetLon!,
                    plan!.reachable
                        ? '${s['escape.headFor']} +${plan!.climbM!.round()} m'
                        : s['escape.noHighGround'],
                    kind: MapMarkKind.destination),
            ],
            route: plan?.targetLat == null
                ? null
                : [
                    [place.lat, place.lon],
                    [plan!.targetLat!, plan!.targetLon!],
                  ],
          ),
        if (dem != null)
          Padding(
            padding: const EdgeInsets.only(top: 6, bottom: 2),
            child: Text(
              '${s['escape.mapNote']} · ${plan == null ? s['escape.mapBefore'] : s['escape.mapAfter']}',
              style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 11),
            ),
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
        if (note != null) Text(note!, style: const TextStyle(color: PahiroTheme.warn)),
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
                color: e.reachable ? PahiroTheme.ink : PahiroTheme.danger,
              ),
            ),
            const SizedBox(height: 8),
            if (e.reachable)
              Text(
                '${e.fromElevationM.toStringAsFixed(0)} m → '
                '${e.targetElevationM!.toStringAsFixed(0)} m · '
                '~${e.walkMinutes!.toStringAsFixed(0)} min',
                style: const TextStyle(color: PahiroTheme.inkMuted),
              ),
            const SizedBox(height: 12),
            Text(escape.adviceNe(e), style: const TextStyle(fontSize: 16, height: 1.6)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  onPressed: () async {
                    // speak() returns false when there is no engine behind it, which is always.
                    // A control that is pressed and does nothing is the same defect as one that
                    // never rendered, so the false is shown instead of discarded.
                    final ok = await speaker.speak(planSteps.first.ne, 'ne');
                    if (!ok && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(strings['speak.unavailable'])));
                    }
                  },
                  child: Text(strings['escape.speak']),
                ),
                if (e.reachable && planSteps.length > 1)
                  OutlinedButton(
                    onPressed: () async {
                      final ok = await speaker.speak(planSteps[1].ne, 'ne');
                      if (!ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(strings['speak.unavailable'])));
                      }
                    },
                    child: Text(strings['escape.directionOnly']),
                  ),
                // The plan is the one thing here worth handing to somebody else - a neighbour, a
                // family member, whoever is deciding whether to move. It is shared as TEXT rather
                // than a link because this project has no deployed web address: a link would point
                // nowhere, and a message that arrives and opens to nothing is worse than no message.
                OutlinedButton(
                  onPressed: () async {
                    final body = StringBuffer()
                      ..writeln(strings['escape.shareHead'])
                      ..writeln()
                      ..writeln(strings['escape.shareWhere']);
                    for (final st in planSteps) {
                      body.writeln('- ${st.ne}');
                    }
                    body
                      ..writeln()
                      ..writeln(strings['escape.shareNote']);
                    try {
                      await SharePlus.instance.share(ShareParams(text: body.toString()));
                    } catch (_) {
                      // Same rule as speech: a control that cannot act says so rather than nothing.
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(strings['speak.unavailable'])));
                      }
                    }
                  },
                  child: Text(strings['escape.share']),
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
                        style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 12)),
                  ],
                ),
              ),
            const Divider(height: 26),
            Text(escape.terrainCaveat,
                style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 11, height: 1.5)),
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

  // Whether the phone is ACTUALLY radiating.
  //
  // Until this existed, the beacon tab encoded a frame and then decoded its own output through
  // `beacon.relay(f)` in the same process. The codec was real and tested; the radio was not there at
  // all, and there was no Bluetooth permission in the manifest to have made it possible. The screen
  // said the distress call travels inside the advertisement, and the phone was silent.
  final _ble = FlutterBlePeripheral();
  bool advertising = false;
  String? advNote;

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

  /// Put the frame on the air.
  ///
  /// The payload rides as manufacturer-specific data, which is the one field a legacy advertisement
  /// lets an application define freely - that is the trick the codec was written for. Everything here
  /// can fail and every failure is SHOWN rather than swallowed: a beacon that silently does not
  /// transmit is the worst possible version of this feature, and it is the version that shipped.
  Future<void> _toggleAdvertise() async {
    if (advertising) {
      try {
        await _ble.stop();
      } catch (_) {}
      if (mounted) setState(() { advertising = false; advNote = null; });
      return;
    }

    final f = frame;
    if (f == null) return;
    final s = widget.strings;
    try {
      if (!await _ble.isSupported) {
        if (mounted) setState(() => advNote = s['beacon.noAdapter']);
        return;
      }
      final state = await _ble.start(
        advertiseData: AdvertiseDataCore(
          // A 16-bit service UUID, not the 128-bit form, and the size is the reason.
          //
          // A legacy advertisement is 31 bytes. Flags take 3, a 128-bit UUID takes 16, and the frame
          // is 20 - which is 39, and the radio refuses it. The first attempt on the handset came back
          // onAdvertisingSetStarted(0, -7, 0), an error status. The short form is resolved against
          // the Bluetooth base UUID and costs 2 bytes, which fits with room to spare.
          serviceUuid: 'F22E',
          manufacturerId: 0x02E5, // unassigned by the Bluetooth SIG; claimed here for Pahiro
          manufacturerData: f,
        ),
      );
      if (!mounted) return;
      setState(() {
        advertising = state == PeripheralBluetoothState.ready ||
            state == PeripheralBluetoothState.granted;
        advNote = advertising ? null : '${s['beacon.notReady']} (${state.name})';
      });
    } catch (e) {
      if (mounted) setState(() { advertising = false; advNote = '${s['beacon.failed']} $e'; });
    }
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
            style: const TextStyle(color: PahiroTheme.inkMuted, height: 1.5)),
        const SizedBox(height: 16),
        FilledButton(onPressed: _build, child: Text(s['beacon.encode'])),
        const SizedBox(height: 10),
        // The radio. Building a frame and transmitting it are different acts, and until this round
        // only the first existed - so the screen said a distress call travels inside the
        // advertisement while the phone stayed silent.
        if (frame != null)
          FilledButton.icon(
            onPressed: _toggleAdvertise,
            icon: Icon(advertising ? Icons.stop_circle_outlined : Icons.podcasts),
            label: Text(advertising ? s['beacon.stop'] : s['beacon.advertise']),
            style: FilledButton.styleFrom(
              backgroundColor: advertising ? PahiroTheme.danger : null,
            ),
          ),
        if (frame != null) ...[
          const SizedBox(height: 8),
          Text(
            advertising ? s['beacon.onAir'] : s['beacon.offAir'],
            style: TextStyle(
              color: advertising ? PahiroTheme.safe : PahiroTheme.warn,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
        if (advNote != null) ...[
          const SizedBox(height: 6),
          Text(advNote!, style: const TextStyle(color: PahiroTheme.danger, fontSize: 12)),
        ],
        const SizedBox(height: 16),
        if (frame != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // THE FRAME CARD WAS PART ENGLISH IN A NEPALI APP - the same defect as the
                  // Settings card, on a screen I had already photographed once without noticing.
                  // "2 people", "position", "ttl ... hops ... (relayed once)" and the Flutter line
                  // were all literals; only the tab name and the button above them were translated.
                  Text(
                    s.lang == AppLang.ne
                        ? '${frame!.length} ${s['beacon.bytes']} · '
                            '${beacon.maxAdBytes - frame!.length} बाँकी '
                            '${beacon.maxAdBytes} मध्ये'
                        : '${frame!.length} ${s['beacon.bytes']} · '
                            '${beacon.maxAdBytes - frame!.length} spare of ${beacon.maxAdBytes}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  SelectableText(beacon.hexOf(frame!),
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                  const SizedBox(height: 10),
                  if (decoded != null) ...[
                    // The codec is shared with the JavaScript side and its peopleText is English,
                    // so the Nepali is composed here from the decoded NUMBERS rather than by
                    // changing a byte-parity codec to satisfy a label. Localising a codec to fix a
                    // caption is how two implementations drift apart.
                    Text(
                      s.lang == AppLang.ne
                          ? '${decoded!.people == 0 ? 'कति जना थाहा छैन' : decoded!.people >= beacon.maxPeople ? '${beacon.maxPeople}+ जना' : '${decoded!.people} जना'}'
                              ' · ${const {
                                  'info': 'जानकारी',
                                  'concern': 'चासो',
                                  'urgent': 'जरुरी',
                                  'critical': 'अत्यावश्यक',
                                }[decoded!.severity] ?? decoded!.severity}'
                          : '${decoded!.peopleText} · ${decoded!.severity}',
                    ),
                    Text(decoded!.hasPosition
                        ? '${s.lang == AppLang.ne ? 'स्थान' : 'position'} '
                            '${decoded!.lat!.toStringAsFixed(5)}, '
                            '${decoded!.lon!.toStringAsFixed(5)}'
                        : (s.lang == AppLang.ne ? 'स्थान थाहा छैन' : 'no position fix')),
                    Text(s.lang == AppLang.ne
                        ? 'ttl ${decoded!.ttl} · ${decoded!.hops} पटक अगाडि बढेको'
                        : 'ttl ${decoded!.ttl} · hops ${decoded!.hops} (relayed once)'),
                  ],
                  const SizedBox(height: 10),
                  Text(
                      s.lang == AppLang.ne
                          ? 'बाइट हावामा पठाउन सक्ने एप हो यो। ब्राउजरले सक्दैन।'
                          : 'A Flutter app can put bytes on the air. A browser cannot.',
                      style: const TextStyle(color: PahiroTheme.primary, fontSize: 12),
                      textAlign: TextAlign.center),
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
        // An empty screen that says only "nothing here" cannot be told apart from a broken one.
        // The board says what it is for and why it may be empty, so a person who sees it knows
        // whether to wait, to move closer to other phones, or to stop trusting the app.
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(strings['board.empty'],
                style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 16),
                textAlign: TextAlign.center),
            const SizedBox(height: 12),
            Text(strings['board.empty_why'],
                style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 13),
                textAlign: TextAlign.center),
          ],
        ),
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
                // THE CARD WAS ENGLISH IN A NEPALI-FIRST APP. The heading above it was
                // "यो फोनमा के चल्छ" and the two lines under it were not translated, so a Nepali
                // user read a Nepali question and an English answer - on the one screen that
                // explains what the model costs them.
                Text(
                  strings.lang == AppLang.ne && f.tier.noteNe.isNotEmpty
                      ? '${f.tier.name} — ${f.tier.noteNe}'
                      : '${f.tier.name} — ${f.tier.note}',
                  style: const TextStyle(height: 1.5),
                ),
                const SizedBox(height: 8),
                Text(
                  strings.lang == AppLang.ne
                      ? 'करिब ${f.tier.ramMb.toStringAsFixed(0)} MB स्मृति चाहिन्छ, '
                          '${f.tier.weightsMb.toStringAsFixed(0)} MB डिस्कमा'
                      : 'needs ~${f.tier.ramMb.toStringAsFixed(0)} MB resident, '
                          '${f.tier.weightsMb.toStringAsFixed(0)} MB on disk',
                  style: const TextStyle(color: PahiroTheme.inkMuted, fontSize: 12),
                ),
                if (f.tier.weightsMb == 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(strings['settings.noModel'],
                        style: const TextStyle(color: PahiroTheme.primary, fontSize: 12)),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// When to go — twelve bars, honest about which four were checked.
///
/// Green months are the ones cross-checked against this project's own CHIRPS measurement; grey are
/// model output alone. Where a region FAILED that check the strip says so rather than drawing twelve
/// equally confident bars over a figure that should not be quoted. No month is labelled good or bad,
/// because a farmer, a trekker and a paraglider want different weather from the same month.
///
/// Top-level rather than a method, so it can be appended without touching the class structure.
Widget seasonStrip(L10n s, seasons.SeasonGuide guide, double lat, double lon) {
  final region = guide.nearest(lat, lon);
  if (region == null) return const SizedBox.shrink();
  final maxRain = region.months
      .map((m) => m.rainMmPerDay)
      .fold<double>(0.01, (a, b) => a > b ? a : b);
  const barMax = 84.0;
  return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(s['walk.seasons'], style: const TextStyle(fontWeight: FontWeight.w700)),
    const SizedBox(height: 2),
    Text(region.name, style: const TextStyle(fontSize: 12, color: PahiroTheme.inkMuted)),
    const SizedBox(height: 8),
    SizedBox(
      height: barMax + 22,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: region.months.map((m) {
          final h = (m.rainMmPerDay / maxRain) * barMax;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.5),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(m.rainMmPerDay.toStringAsFixed(0),
                      style: const TextStyle(fontSize: 8, color: PahiroTheme.inkMuted)),
                  Container(
                    height: h.clamp(2.0, barMax),
                    decoration: BoxDecoration(
                      color: m.validated
                          ? PahiroTheme.safe
                          : PahiroTheme.inkMuted,
                      borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(m.name.substring(0, 1),
                      style: const TextStyle(fontSize: 9, color: PahiroTheme.inkMuted)),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    ),
    const SizedBox(height: 6),
    Text(s['walk.validated'], style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
    if (!region.reliable) ...[
      const SizedBox(height: 4),
      Text(s['walk.unreliable'],
          style: const TextStyle(fontSize: 11, color: PahiroTheme.danger)),
    ],
    const SizedBox(height: 4),
    Text(s['walk.seasonsNote'], style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
  ]);
}

/// Look around the valley — the 360-degree render, draggable, offline.
///
/// The image is the equirectangular panorama the web app serves, bundled into the APK rather than
/// fetched, because the places a valley view matters most are the places with no signal. Dragging
/// left and right walks the full 360 degrees; the aspect ratio is 2:1 by construction, which is what
/// an equirectangular projection is.
///
/// It is NOT a photograph. It is a silhouette rendered from the elevation grid this app already
/// carries: shape, no trees, no buildings, and a gradient sky. The caption says so.
class PanoramaView extends StatefulWidget {
  final String regionKey;
  final String title;
  final String caption;
  final String fallback;
  final String vrLabel;
  final VoidCallback onVr;
  const PanoramaView({super.key, required this.regionKey,
                      required this.title, required this.caption,
                      required this.fallback,
                      required this.vrLabel, required this.onVr});

  @override
  State<PanoramaView> createState() => _PanoramaViewState();
}

class _PanoramaViewState extends State<PanoramaView> {
  final _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const h = 150.0;                 // 2:1, so 300 wide per full turn at this height
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: SizedBox(
          height: h,
          child: Scrollbar(
            controller: _controller,
            child: SingleChildScrollView(
              controller: _controller,
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              child: Image.asset(
                'assets/panoramas/${widget.regionKey}.png',
                height: h,
                fit: BoxFit.fitHeight,
                errorBuilder: (_, _, _) => Container(
                  height: h,
                  alignment: Alignment.center,
                  color: PahiroTheme.hairline,
                  child: Text(widget.fallback,
                      style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
                ),
              ),
            ),
          ),
        ),
      ),
      const SizedBox(height: 4),
      Text(widget.caption,
          style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
      const SizedBox(height: 4),
      Text('← 360° →',
          style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
      const SizedBox(height: 8),
      // The same image, but somewhere you look rather than something you drag.
      OutlinedButton.icon(
        onPressed: widget.onVr,
        icon: const Icon(Icons.view_in_ar, size: 16),
        label: Text(widget.vrLabel),
      ),
    ]);
  }
}

/// Who is responsible for the ground you are standing on.
///
/// Self-contained: it loads its own asset, so nothing has to be threaded through the Escape screen's
/// state to show it. Every complaint portal in Nepal routes to a municipality, and a municipality can
/// say "not ours" and be finished - this names the office the routing key holds responsible AND the
/// local unit that office belongs to, with the unit's own gov.np site, so a letter can be addressed
/// to something that exists.
///
/// It says what it does not know: 119 of the 613 documented slopes name a unit the national
/// gazetteer does not carry, and for those it reports the office without inventing an address.
abstract class DutyLoader {
  Future<DutyIndex> load();
}

class AssetDutyLoader implements DutyLoader {
  const AssetDutyLoader();
  @override
  Future<DutyIndex> load() async =>
      DutyIndex.parse(await rootBundle.loadString('assets/complaint-index.json'));
}


/// A government address, shown as its publisher gives it, with one addition.
///
/// Fourteen of these are plain http. Dialling every one over TLS found six with no HTTPS listener at
/// all, so rewriting them to https would not secure them, it would break them - and a dead link on the
/// screen whose entire purpose is reaching a duty holder is worse than an unencrypted working one.
/// What is possible without changing a single address is to say which is which.
///
/// The note arrives as a finished string because neither panel owns the language: DutyPanel and
/// PlacesPanel both take translated text as fields, and reaching for L10n inside them is what broke
/// the first attempt at this.
String siteLabel(String url, String note) =>
    url.startsWith('http://') ? '$url  \u00b7  $note' : url;

class DutyPanel extends StatefulWidget {
  final String strings;
  final double lat;
  final double lon;
  final String title;
  final String caption;
  final String noAddress;
  final String defaultNote;
  final String draftButton;
  final String letterNote;
  /// Appended to a government address published over plain http.
  final String unencrypted;
  final bool nepali;

  /// Shown when the data could not be loaded. A panel that disappears is indistinguishable from a
  /// panel with nothing to say, which is the "gap in the map" problem in the app's own furniture.
  final String failedLabel;

  /// Injectable for the same reason the trail, season and DEM loaders are: a panel that reads an
  /// asset directly hides itself when the asset cannot be resolved, which in a widget test means the
  /// feature is untestable by name and in production means a missing file is a missing panel with
  /// no signal anywhere.
  final DutyLoader loader;
  const DutyPanel({super.key, required this.strings, required this.lat, required this.lon,
                   required this.unencrypted,
                   required this.title, required this.caption, required this.noAddress,
                   required this.defaultNote, required this.draftButton,
                   required this.letterNote, required this.nepali, required this.failedLabel,
                   this.loader = const AssetDutyLoader()});

  @override
  State<DutyPanel> createState() => _DutyPanelState();
}

class _DutyPanelState extends State<DutyPanel> {
  Duty? _duty;
  double? _distanceM;
  bool _tried = false;
  bool _failed = false;
  bool _showLetter = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final idx = await widget.loader.load();
      final d = idx.nearest(widget.lat, widget.lon);
      if (!mounted) return;
      setState(() {
        _duty = d;
        _distanceM = d == null
            ? null
            : haversineM(widget.lat, widget.lon, d.lat, d.lon);
        _tried = true;
      });
    } catch (_) {
      if (mounted) setState(() { _tried = true; _failed = true; });
    }
  }

  /// The complaint, composed on the phone from the row.
  ///
  /// It cites the section that obliges the named office, so it cannot be bounced as "not ours"
  /// without somebody deciding that on paper. It says on its face that it was drafted
  /// automatically and starts no proceeding - the citizen sends it and keeps the receipt.
  String _letter(Duty d, bool nepali) {
    final place = d.hasAddress
        ? (nepali
            ? 'यो स्थान ${d.unit}${d.district != null ? ', ${d.district} जिल्ला' : ''} भित्र पर्छ।'
            : 'This location falls in ${d.unit}${d.district != null ? ', ${d.district} district' : ''}'
              '${d.site != null ? ' (${d.site})' : ''}.')
        : (nepali
            ? 'यो स्थानको नगरपालिका पहिचान गर्न सकिएन।'
            : 'No local unit could be matched for this place.');
    if (nepali) {
      return 'विषय: ${d.title} को जोखिमबारे जानकारी\n\n'
          'श्रीमान्/श्रीमती प्रमुखज्यू,\n\n'
          'मैले ${d.lat.toStringAsFixed(5)}, ${d.lon.toStringAsFixed(5)} निर्देशांकको ढलानमा '
          'जोखिम देखेको छु।\n\n'
          '$place\n\n'
          'स्थानीय सरकार सञ्चालन ऐन, २०७४ को धारा १२(२)(ग) बमोजिम सडकसँग जोडिएको पहिरो '
          'हटाउने दायित्व ${d.officeFor(true)} को हो।\n\n'
          'कृपया यो स्थानको निरीक्षण गरी आवश्यक व्यवस्था मिलाउनुहुन अनुरोध गर्दछु। '
          'यो पत्र स्वचालित रूपमा तयार भएको हो र यसले कुनै कानुनी कारबाही सुरु गर्दैन।\n\n'
          '[तपाईंको नाम]\n[सम्पर्क नम्बर]\n[मिति]';
    }
    return 'Subject: Report - ${d.title}\n\n'
        'Dear Sir/Madam,\n\n'
        'I am reporting a slope at ${d.lat.toStringAsFixed(5)}, ${d.lon.toStringAsFixed(5)}.\n\n'
        '$place\n\n'
        'Under the Local Government Operation Act 2074, s.12(2)(c), the duty to remove landslides '
        'affecting roads rests with ${d.office}.\n\n'
        'I request an inspection and appropriate action. This letter was drafted automatically and '
        'does not by itself start any legal proceeding.\n\n'
        '[Your name]\n[Contact number]\n[Date]';
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) return loadFailed(widget.failedLabel);
    if (!_tried || _duty == null) return const SizedBox.shrink();
    final d = _duty!;
    final km = (_distanceM ?? 0) / 1000;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(d.title, style: const TextStyle(fontSize: 13)),
          const SizedBox(height: 2),
          Text('${km.toStringAsFixed(1)} km', style: const TextStyle(
              fontSize: 11, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 8),
          if (d.hasAddress) ...[
            Text('${d.unit} — ${d.district ?? ''}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            if (d.site != null)
              Text(siteLabel(d.site!, widget.unencrypted),
                  style: const TextStyle(fontSize: 11, color: PahiroTheme.primary)),
          ] else
            Text(widget.noAddress,
                style: const TextStyle(fontSize: 11, color: PahiroTheme.danger)),
          const SizedBox(height: 8),
          // Same translation table as the letter: fixing the caption and leaving the card
          // English would be two vocabularies on one screen.
          Text(d.officeFor(widget.nepali),
              style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 4),
          Text(d.legal, style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 8),
          Text(widget.defaultNote,
              style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 4),
          Text(widget.caption,
              style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: () => setState(() => _showLetter = !_showLetter),
              child: Text(widget.draftButton),
            ),
          ),
          if (_showLetter) ...[
            const SizedBox(height: 4),
            Text(widget.letterNote,
                style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
            const SizedBox(height: 6),
            SelectableText(_letter(d, widget.nepali),
                style: const TextStyle(fontSize: 12, height: 1.5)),
          ],
        ]),
      ),
    );
  }
}

/// The flood scenario, step by step, on the phone.
///
/// The step text is bundled in both languages. Four of the six steps are LIVE - they are the panels
/// above, computed from data the phone carries - and two are measurements made elsewhere in this
/// project and labelled as cited rather than as computed. The card says which is which, because a
/// demo that blurs measured and cited numbers is how a product ends up claiming more than it did.
class DemoPanel extends StatefulWidget {
  final String title;
  final String blurb;
  final String runLabel;
  final String nextLabel;
  final String liveLabel;
  final String citedLabel;
  final bool nepali;
  final String failedLabel;
  const DemoPanel({super.key, required this.title, required this.blurb, required this.runLabel,
                   required this.nextLabel, required this.liveLabel, required this.citedLabel,
                   required this.nepali, required this.failedLabel});

  @override
  State<DemoPanel> createState() => _DemoPanelState();
}

class _DemoPanelState extends State<DemoPanel> {
  List<Map<String, dynamic>> _steps = const [];
  int _shown = 0;
  bool _loaded = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final raw = jsonDecode(await rootBundle.loadString('assets/demo-script.json'));
      final steps = (raw['steps'] as List).cast<Map<String, dynamic>>();
      if (mounted) setState(() { _steps = steps; _loaded = true; });
    } catch (_) {
      if (mounted) setState(() { _loaded = true; _failed = true; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) return loadFailed(widget.failedLabel);
    if (!_loaded || _steps.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(widget.blurb, style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
          const SizedBox(height: 10),
          if (_shown == 0)
            FilledButton(onPressed: () => setState(() => _shown = 1), child: Text(widget.runLabel))
          else ...[
            // NOT named `s`. In the shell that identifier is the L10n instance, and reusing it for
            // a step map made the localisation guard read the step number as a missing translation
            // key - correctly, because the same name meant two things in one file, which is how a
            // lookup ends up resolving against the wrong table. (The guard scans raw text, so even
            // writing the old expression in this comment trips it.)
            for (final step in _steps.take(_shown)) ...[
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${step['n']}.  ', style: const TextStyle(fontWeight: FontWeight.w700)),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(widget.nepali ? step['ne'] as String : step['en'] as String,
                        style: const TextStyle(fontSize: 12, height: 1.5)),
                    const SizedBox(height: 2),
                    Text('${step['live'] == true ? widget.liveLabel : widget.citedLabel} · '
                        '${step['src']}',
                        style: TextStyle(
                            fontSize: 10,
                            color: step['live'] == true
                                ? PahiroTheme.safe
                                : PahiroTheme.inkMuted)),
                  ]),
                ),
              ]),
              const SizedBox(height: 10),
            ],
            if (_shown < _steps.length)
              FilledButton(
                onPressed: () => setState(() => _shown += 1),
                child: Text('${widget.nextLabel} ($_shown/${_steps.length})'),
              ),
          ],
        ]),
      ),
    );
  }
}

/// Major places near you, on the phone, offline.
///
/// A list rather than a map of 277 dots. The escape screen has a hillshaded terrain map drawn from
/// the bundled elevation grid, but that renders relief, not a national scatter of points: drawing
/// every local unit would want a projection, a viewport and panning, for a screen whose whole job is
/// telling you which office is responsible. The data is the same file either way.
///
/// It says how many of the country's units it has: 277 of 753, because a unit only has a position
/// here if documented slopes inside it name it. And it repeats the file's own accuracy note - a
/// position is the mean of those slopes, not a town centre.

class PlacesPanel extends StatefulWidget {
  final String title;
  final String caption;
  final String slopesLabel;
  final String trailsLabel;
  /// Appended to a government address published over plain http.
  final String siteNote;
  final bool nepali;
  final String failedLabel;
  final double lat;
  final double lon;
  const PlacesPanel({super.key, required this.title, required this.caption,
                     required this.slopesLabel, required this.trailsLabel,
                     required this.siteNote,
                     required this.nepali, required this.lat, required this.lon,
                     required this.failedLabel});

  @override
  State<PlacesPanel> createState() => _PlacesPanelState();
}

class _PlacesPanelState extends State<PlacesPanel> {
  List<(GeoPlace, double)> _near = const [];
  bool _loaded = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final raw = await rootBundle.loadString('assets/places.geojson');
      final list = PlaceList.parse(raw);
      final near = list.nearest(widget.lat, widget.lon, limit: 5);
      if (mounted) setState(() { _near = near; _loaded = true; });
    } catch (_) {
      if (mounted) setState(() { _loaded = true; _failed = true; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) return loadFailed(widget.failedLabel);
    if (!_loaded || _near.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      for (final (place, metres) in _near)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text(widget.nepali && place.nameNe != null
                        ? '${place.nameNe} · ${place.name}'
                        : place.name,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ),
              Text('${(metres / 1000).toStringAsFixed(0)} km',
                  style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
            ]),
            Text([
              if (place.district != null) place.district!,
              if (place.population != null) '${place.population}',
              '${widget.slopesLabel} ${place.slopes}',
              '${widget.trailsLabel} ${place.trails}',
            ].join(' · '),
                style: const TextStyle(fontSize: 11, color: PahiroTheme.inkMuted)),
            if (place.hasWebsite)
              Text(siteLabel(place.site!, widget.siteNote),
                  style: const TextStyle(fontSize: 10, color: PahiroTheme.primary)),
          ]),
        ),
      Text(widget.caption, style: const TextStyle(fontSize: 10, color: PahiroTheme.inkMuted)),
    ]);
  }
}

/// One way for a panel to say it could not load.
///
/// Three panels used to return an empty box when their asset failed, which is indistinguishable from
/// having nothing to say. This project's whole argument is that a user must be able to tell "nothing
/// is here" from "we could not look" - and that has to be true of the app's own furniture, not only
/// of the map data.
Widget loadFailed(String label) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(label,
          style: const TextStyle(fontSize: 11, color: PahiroTheme.danger)),
    );
