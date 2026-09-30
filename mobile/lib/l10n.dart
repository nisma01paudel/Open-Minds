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
    'beacon.bytes': 'बाइट',
    'board.title': 'बोर्ड',
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
    'beacon.bytes': 'bytes',
    'board.title': 'Board',
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

  bool get chosen => value != null;

  void choose(AppLang lang) => value = lang;

  L10n get strings => L10n(value ?? AppLang.en);
}
