/// Language, chosen on first run and used everywhere afterwards.
///
/// A foreigner opens this app in Nepal and the first screen is in Nepali, or a Nepali speaker
/// opens it and every instruction is in English at the moment they are least able to translate.
/// Both are avoidable. So the language is picked before anything else and remembered.
///
/// WHY ONLY TWO LANGUAGES
/// ----------------------
/// Nepali and English, translated as well as this project can honestly manage. Adding a third is
/// one entry in [translations] - but adding one we cannot write correctly would put a wrong
/// instruction in front of someone running from water, which is worse than English. The right
/// way to add a language is for a speaker of it to add the map.
///
/// WHY THE NEPALI IS FIRST IN THE DATA
/// -----------------------------------
/// The strings that save a life are authored in Nepali and then translated, not the other way
/// round. `escape.dart` keeps its own spoken vocabulary for the same reason, and a test pins the
/// two against each other so the surfaces cannot drift into saying different things.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The languages this app can actually speak, with their own names for themselves - a language
/// picker that labels Nepali as "Nepali" is useless to the person who needs it.
enum AppLang {
  ne('ne', 'नेपाली', 'Nepali'),
  en('en', 'English', 'English');

  const AppLang(this.code, this.endonym, this.englishName);
  final String code;
  final String endonym;
  final String englishName;

  static AppLang? fromCode(String? code) {
    for (final l in AppLang.values) {
      if (l.code == code) return l;
    }
    return null;
  }
}

/// Every user-facing string, per language. Missing keys fall back to English rather than showing
/// a raw key to someone in a flood.
class L10n {
  final AppLang lang;
  const L10n(this.lang);

  String call(String key) =>
      translations[lang.code]?[key] ?? translations['en']![key] ?? key;

  String operator [](String key) => call(key);

  /// For the one screen that must be readable before a language is chosen: both languages at
  /// once, so the choice can be made without already knowing either.
  static String both(String key) =>
      '${translations['ne']![key] ?? key}\n${translations['en']![key] ?? key}';
}

/// Kept flat and small on purpose. A nested structure reads better in an editor and worse when
/// a translator has to diff it.
const Map<String, Map<String, String>> translations = {
  'ne': {
    'app.title': 'पहिरो',
    'app.tagline': 'कहाँ भाग्ने, र कति माथि',
    'lang.choose': 'भाषा छान्नुहोस्',
    'lang.chooseHint': 'पछि सेटिङमा फेर्न सकिन्छ।',
    'lang.continue': 'अगाडि बढ्नुहोस्',
    'tab.escape': 'भाग्नुहोस्',
    'tab.beacon': 'बीकन',
    'tab.board': 'बोर्ड',
    'walk.title': 'यहाँबाट कहाँ पदयात्रा गर्न सकिन्छ',
    'walk.from': 'स्थान',
    'walk.within': 'दायरा',
    'walk.none': 'यो दायराभित्र कुनै बाटो नक्सामा छैन। यसको अर्थ बाटो नै छैन भन्ने होइन — कसैले नक्सामा कोरेको छैन।',
    'walk.loadfail': 'पदयात्रा डाटा खोल्न सकिएन।',
    'walk.caveat': 'बाटोको डाटा OpenStreetMap बाट हो र नेपालका सबै पैदल बाटो नक्सामा छैनन्। समय उकालो नगणेर अनुमान गरिएको हो।',
    'tab.walk': 'पदयात्रा',
    'tab.settings': 'सेटिङ',
    'escape.title': 'भाग्नुहोस् — कहाँ, र कति माथि',
    'escape.blurb': '"बाढी आउँदैछ" भन्ने चेतावनीले सबैभन्दा महत्त्वपूर्ण कुरा छुटाउँछ: '
        'कुन दिशा, र कति माथि। यो फोनमै, सञ्जाल नभएपनि, उचाइको डेटाबाट गणना गरिन्छ।',
    'escape.place': 'ठाउँ',
    'escape.rise': 'पानी कति माथि आउँछ (अनुमान)',
    'escape.go': 'यहाँबाट कहाँ जाने?',
    'escape.speak': '🔊 सुन्नुहोस्',
    'escape.directionOnly': '🔊 दिशा मात्र',
    'escape.notLoaded': 'उचाइको डेटा लोड भएन।',
    'escape.offline': 'यो सबै फोनमै गणना हुन्छ — इन्टरनेट चाहिँदैन।',
    'escape.noGround': 'नजिकै सुरक्षित उचाइ छैन',
    'escape.noVoice': 'यो फोनमा नेपाली आवाज छैन — पाठ मात्र देखाइएको छ।',
    'beacon.title': 'बीकन — जोड्नु नपर्ने सन्देश',
    'beacon.blurb': 'सङ्कटको सन्देश ब्लुटुथ विज्ञापनभित्रै जान्छ। जोड्नु पर्दैन, '
        'जोडिनु पर्दैन, र बोक्ने फोनमा यो एप खोल्नु पनि पर्दैन।',
    'beacon.encode': 'नमुना फ्रेम बनाउनुहोस्',
    'beacon.advertise': 'बीकन बाल्नुहोस्',
    'beacon.stop': 'बीकन बन्द गर्नुहोस्',
    'beacon.onAir': 'अहिले प्रसारण भइरहेको छ — यो फोनले वरपरका फोनहरूमा सन्देश पठाइरहेको छ।',
    'beacon.offAir': 'अहिले केही प्रसारण भइरहेको छैन। तलको बीकन बाल्नुहोस् — फ्रेम बनाउनु मात्र पुग्दैन।',
    'beacon.noAdapter': 'यो फोनमा ब्लुटुथ बीकन चल्दैन।',
    'beacon.notReady': 'ब्लुटुथ तयार भएन',
    'beacon.failed': 'बीकन बाल्न सकिएन:',
    'beacon.bytes': 'बाइट',
    'board.title': 'बोर्ड',
    'walk.look': 'उपत्यका हेर्नुहोस्',
    'duty.title': 'यो जमिन कसको जिम्मामा',
    'demo.title': 'बाढी आउँदा एपले के गर्छ',
    'load.failed': 'यो भाग लोड हुन सकेन — सामग्री भेटिएन।',
    'speak.unavailable': 'यो फोनमा वाचन उपलब्ध छैन — निर्देशन पढ्नुहोस्।',
    'escape.share': 'पठाउनुहोस्',
    'escape.you': 'तपाईं यहाँ',
    'escape.headFor': 'यता जानुहोस्',
    'escape.noHighGround': 'सुरक्षित उचाइ भेटिएन',
    'escape.mapNote': 'उचाइको ग्रिडबाट यही फोनमै कोरिएको',
    'escape.mapFailed': 'यो फोनमा उचाइको नक्सा कोर्न सकिएन।',
    'duty.unencrypted': 'यो कडी इन्क्रिप्टेड छैन',
    'escape.mapBefore': 'योजना हेर्न तल थिच्नुहोस्',
    'escape.mapAfter': 'देखाइएको बाटो योजना हो',
    'escape.shareHead': 'पहिरो — भाग्ने योजना (यो फोनमै गणना गरिएको)',
    'escape.shareWhere': 'यो क्षेत्रीय सुझाव हो, स्थानीय निर्देशन पालना गर्नुहोस्।',
    'escape.shareNote': 'यो यही फोनमा, इन्टरनेट बिना गणना गरिएको हो।',
    'places.title': 'नजिकका प्रमुख ठाउँ',
    'places.caption': 'यी ७५३ मध्ये २७७ स्थानीय इकाई हुन् जसलाई यहाँ राख्न सकियो — '
        'निर्देशांक ती ठाउँका अभिलेखित ढलानहरूको औसत हो, नगर केन्द्र होइन।',
    'places.slopes': 'ढलान',
    'places.trails': 'पदमार्ग',
    'demo.blurb': 'हरियो चरण यही फोनमै गणना हुन्छ; खैरा यही परियोजनाको अन्त कतै गरिएको नाप हो।',
    'demo.run': 'परिदृश्य चलाउनुहोस्',
    'demo.next': 'अर्को चरण',
    'demo.live': 'यही फोनमै गणना',
    'demo.cited': 'यहाँ उद्धृत',
    'duty.draft': 'उजुरीको मस्यौदा देखाउनुहोस्',
    'duty.letterNote': 'यो मस्यौदा हो। एपले पठाउँदैन, हस्ताक्षर गर्दैन र प्राप्ति पनि गर्दैन — '
        'तपाईंले पठाउनुहोस् र रसिद राख्नुहोस्।',
    'duty.where': 'यो जमिनको जिम्मा माथि देखाइएको निकायको हो।',
    'duty.noAddress': 'यो ठाउँको नगरपालिका पहिचान गर्न सकिएन — ठेगाना बनाइएको छैन।',
    'duty.default': 'तल देखाइएको कार्यालय सडकको लागि पूर्वनिर्धारित हो, हरेक जग्गाको कानुनी '
        'निर्धारण होइन। राजमार्ग, वन वा निजी जग्गामा जिम्मेवार निकाय फरक पर्छ।',
    'walk.noPanorama': 'यो क्षेत्रको चित्र उपलब्ध छैन',
    'walk.lookNote': 'यो तस्बिर होइन — उचाइको डेटाबाट बनाइएको ३६०° को चित्र हो। रूख, घर वा '
        'जमिनको रङ यसमा छैन; आकृति मात्र। दायाँबायाँ तान्नुहोस्।',
    'walk.seasons': 'कहिले जाने',
    'walk.seasonsNote': 'यी बाह्र महिना यहाँका लागि मापन गरिएका हुन्, तर कुनै महिनालाई राम्रो वा '
        'नराम्रो भनिएको छैन। किसान, पदयात्री र प्याराग्लाइडरले एउटै महिनाबाट फरक मौसम चाहन्छन्।',
    'walk.validated': 'हरियो महिना यही परियोजनाको नापसँग जाँचिएका; खैरा केवल मोडेलको अनुमान।',
    'walk.unreliable': 'यो क्षेत्रको वर्षाको अङ्क जाँचमा उत्तीर्ण भएन — यसलाई उद्धृत नगर्नुहोस्।',
    'board.empty': 'अहिले कुनै सन्देश छैन।',
    'board.empty_why': 'यो बोर्डले नजिकैका फोनबाट ब्लुटुथमा आएका सन्देश देखाउँछ। खाली हुनुको अर्थ दुईमध्ये एक हो: कसैले पठाएको छैन, वा नजिकमा अर्को फोन छैन। फोन सँगै राख्नुहोस्।',
    'settings.title': 'सेटिङ',
    'settings.language': 'भाषा',
    'settings.device': 'यो यन्त्र',
    'settings.model': 'यो फोनमा के चल्छ',
    'settings.noModel': 'कुनै मोडेल छैन — तर जीवन बचाउने सबै सुविधा चल्छन्।',
    'settings.caveat': 'यो केवल भू-स्वरूपको जानकारी हो। पुल, नाली वा पानी आफैं देखिँदैन। '
        'पहिले खोलाबाट टाढा जानुहोस्।',
    'common.back': 'पछाडि',
  },
  'en': {
    'app.title': 'Pahiro',
    'app.tagline': 'Which way to run, and how high',
    'lang.choose': 'Choose your language',
    'lang.chooseHint': 'You can change this later in Settings.',
    'lang.continue': 'Continue',
    'tab.escape': 'Escape',
    'walk.title': 'What can I walk from here',
    'walk.from': 'at',
    'walk.within': 'within',
    'walk.none': 'No mapped path within this radius. That does not mean there is nothing to walk — it means nobody has drawn it yet.',
    'walk.loadfail': 'Could not open the trail data.',
    'walk.caveat': 'Trail data is OpenStreetMap and not every Nepali footpath is mapped. Times ignore climbing.',
    'tab.walk': 'Walk',
    'tab.beacon': 'Beacon',
    'tab.board': 'Board',
    'tab.settings': 'Settings',
    'escape.title': 'Escape — which way, and how high',
    'escape.blurb': 'A warning that says "flash flood" leaves out the only decision that '
        'matters: which way, and how far up. This works it out on the phone, from the '
        'elevation data, with the network already gone.',
    'escape.place': 'Place',
    'escape.rise': 'Expected flood rise',
    'escape.go': 'WHERE DO I GO FROM HERE?',
    'escape.speak': '🔊 Speak it',
    'escape.directionOnly': '🔊 Direction only',
    'escape.notLoaded': 'The elevation data did not load.',
    'escape.offline': 'All of this is computed on the phone. No internet needed.',
    'escape.noGround': 'NO REACHABLE HIGH GROUND',
    'escape.noVoice': 'No Nepali voice is installed on this device, so the text is shown '
        'rather than read badly in another language.',
    'beacon.title': 'Beacon — a message that needs no connection',
    'beacon.blurb': 'The distress call travels inside the Bluetooth advertisement itself. No '
        'pairing, no connection, and the phone that carries it does not need this app open.',
    'beacon.encode': 'Build a sample frame',
    'beacon.advertise': 'Start beaconing',
    'beacon.stop': 'Stop beaconing',
    'beacon.onAir': 'Transmitting now — this phone is advertising the frame to every handset in range.',
    'beacon.offAir': 'Nothing is being transmitted. Building a frame does not put it on the air — press the button below.',
    'beacon.noAdapter': 'This phone cannot act as a Bluetooth beacon.',
    'beacon.notReady': 'Bluetooth is not ready',
    'beacon.failed': 'The beacon could not be started:',
    'beacon.bytes': 'bytes',
    'board.title': 'Board',
    'walk.look': 'Look around the valley',
    'duty.title': 'Who is responsible for this ground',
    'demo.title': 'What the app does when a flood comes',
    'load.failed': 'This section could not be loaded — its data is missing.',
    'speak.unavailable': 'Speech is not available on this phone — read the steps.',
    'escape.share': 'Send this',
    'escape.you': 'You are here',
    'escape.headFor': 'Head for',
    'escape.noHighGround': 'No safe high ground found',
    'escape.mapNote': 'Relief drawn on this phone from the elevation grid',
    'escape.mapFailed': 'The relief could not be drawn on this phone.',
    'duty.unencrypted': 'not encrypted',
    'escape.mapBefore': 'run the plan to draw the route',
    'escape.mapAfter': 'the line is the plan, not a road',
    'escape.shareHead': 'Pahiro — a way out (computed on this phone)',
    'escape.shareWhere': 'This is regional advice. Follow local instructions.',
    'escape.shareNote': 'Computed on the phone, with no internet.',
    'places.title': 'Major places near you',
    'places.caption': 'These are 277 of Nepal\'s 753 local units - the ones that could be located, '
        'because a position is the mean of the documented slopes inside them, not a town centre.',
    'places.slopes': 'slopes',
    'places.trails': 'trails',
    'demo.blurb': 'Green steps are computed on this phone; grey ones are measurements made '
        'elsewhere in this project and cited here.',
    'demo.run': 'Run the scenario',
    'demo.next': 'Next step',
    'demo.live': 'computed here',
    'demo.cited': 'cited',
    'duty.draft': 'Show a draft complaint',
    'duty.letterNote': 'This is a draft. The app does not send it, sign it or receive it — you send '
        'it and keep the receipt.',
    'duty.where': 'The duty for this ground rests with the body shown above.',
    'duty.noAddress': 'No local unit could be matched for this place — no address is invented.',
    'duty.default': 'The office below is the routing key\'s DEFAULT for a local road, not a '
        'per-parcel legal determination. On a highway, in forest, or on private land the responsible '
        'body differs.',
    'walk.noPanorama': 'No panorama bundled for this region',
    'walk.lookNote': 'Not a photograph — a 360° view rendered from the elevation data. No trees, no '
        'buildings, no ground colour; shape only. Drag left and right.',
    'walk.seasons': 'When to go',
    'walk.seasonsNote': 'These twelve months were measured for here, and no month is called good or '
        'bad. A farmer, a trekker and a paraglider want different weather from the same month.',
    'walk.validated': 'Green months are cross-checked against this project\'s own measurement; '
        'grey are model output only.',
    'walk.unreliable': 'This region failed that check — its rain figures should not be quoted.',
    'board.empty_why': 'This board shows messages that arrived over Bluetooth from nearby phones. Empty means one of two things: nobody has sent one, or no other phone is close enough yet. Put phones near each other.',
    'board.empty': 'Nothing yet.',
    'settings.title': 'Settings',
    'settings.language': 'Language',
    'settings.device': 'This device',
    'settings.model': 'What runs on this phone',
    'settings.noModel': 'No model at all — and every life-saving feature still works.',
    'settings.caveat': 'This is terrain only. It cannot see bridges, culverts or the water. '
        'Move away from the stream first.',
    'common.back': 'Back',
  },
};

/// A [ValueNotifier] so a language change rebuilds the whole tree without a state management
/// dependency. Small enough to be obvious, and it makes the first-run gate trivial to test.
class LanguageController extends ValueNotifier<AppLang?> {
  LanguageController([super.initial]);

  /// Where the choice is remembered between launches.
  ///
  /// The app asked "Choose your language" on every start until this existed, which is the first
  /// thing anybody sees and the wrong first impression for a tool that is otherwise careful. The
  /// choice is the one piece of state worth keeping: it is not derived from anything, and re-asking
  /// is the difference between an app and a web page.
  static const _prefsKey = 'pahiro.lang';

  bool get chosen => value != null;

  void choose(AppLang lang) {
    value = lang;
    // Fire and forget. A device that cannot write preferences still has a working app; it just
    // forgets, and interrupting a language choice to say so would be worse than the forgetting.
    _remember(lang.code);
  }

  static Future<void> _remember(String code) async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setString(_prefsKey, code);
    } catch (_) {
      // The fallback is that the question is asked again, which is not worth an error message.
    }
  }

  /// The language chosen on a previous run, or null on a first run - and null on any failure,
  /// because a preference store that is broken must not stop the app starting.
  static Future<AppLang?> remembered() async {
    try {
      final p = await SharedPreferences.getInstance();
      final code = p.getString(_prefsKey);
      if (code == null) return null;
      for (final l in AppLang.values) {
        if (l.code == code) return l;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  L10n get strings => L10n(value ?? AppLang.en);
}
