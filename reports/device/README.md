# The app, running on an Android device

Not a mock-up and not a render. These are `adb screencap` frames from the release APK installed and
launched on an Android emulator (API 36, x86_64, `/dev/kvm`) on 2026-10-01.

    emulator -avd pahiro -no-window -gpu swiftshader_indirect
    adb install -r mobile/build/app/outputs/flutter-apk/app-release.apk
    adb shell monkey -p np.pahiro.pahiro_field -c android.intent.category.LAUNCHER 1

| frame | what it shows |
|---|---|
| `pahiro-1.png` | the language gate: पहिरो · Pahiro, "कहाँ भाग्ने, र कति माथि", Nepali first |
| `pahiro-3.png` | the escape screen **entirely in Nepali**, place मेलम्ची, water-rise slider |
| `pahiro-walk.png` | the Walk tab: six trails from a 5.4 MB bundle read out of the APK |
| `pahiro-escape-refusal.png` | the escape planner **refusing** at Melamchi, in Nepali, with advice |
| `pahiro-beacon.png` | the Beacon tab: a message that needs no pairing and no app on the carrier |
| `pahiro-offline-airplane.png` | **airplane mode on, network "none", and the trails are identical** |
| `pahiro-beacon-frame.png` | **a real 20-byte advertisement, encoded on the device, in hex** |
| `pahiro-board-empty.png` | the Board with no messages, **and the app explaining why** |
| `pahiro-settings-nepali.png` | Settings after the fix: **the capability card in Nepali** |
| `pahiro-beacon-nepali.png` | the frame card after the fix: **every line in Nepali** |
| `pahiro-walk-seasons.png` | **the Walk tab with when-to-go: twelve bars, four green, Kathmandu warned** |
| `pahiro-walk-panorama.png` | **and look-around: the 360° valley render, on the phone, offline** |
| `pahiro-duty.png` | **who is responsible for the ground, with a real gov.np address and the statute** |
| `pahiro-complaint.png` | **the complaint itself, drafted on the phone, citing the section** |
| `pahiro-demo-panel.png` | the flood scenario: **Run the scenario**, labelled live vs cited |

## What this changes, and what it does not

**Changed:** the app compiles, installs, launches, renders Nepali text, responds to touch, switches
tabs, reads its bundled trail data and lists trails by distance. Fifty rounds of "nothing has run on
a real handset" end here.

**Unchanged, and still stated everywhere:** this is an **emulator**, not a physical phone. No radio
figure has been measured on real hardware - Bluetooth range, Wi-Fi Aware range and battery endurance
are all still somebody else's measurements or modelled from them. An emulator cannot measure a radio.

## The flood scenario, on the phone

    बाढी आउँदा एपले के गर्छ
    हरियो चरण यही फोनमै गणना हुन्छ; खैरा यही परियोजनाको अन्त कतै गरिएको नाप हो।
    [ परिदृश्य चलाउनुहोस् ]

Six steps of the monsoon of 2024, and each one is LABELLED for whether it is computed on this phone
or cited from a measurement made elsewhere in this project. Four are live - the duty routing, the
escape planner, the complaint and the beacon, all of which the phone really does - and two are the
rainfall count and the satellite blindness, which were measured on a machine with the full 613-slope
record.

A demo that blurred measured and cited numbers would be the same failure as every stale caption in
this project, so the distinction is on the screen rather than in a speaker's note.

**Verified, on the second attempt.** The first attempt reported the button rendering but not
advancing, and the reason was my taps: I read the coordinate off the SCALED preview (872x1890) while
the device is 1080x2340, so I pressed at y=900 against a button spanning y=780-879. Tapping y=830
advanced it:

    1. २०२४ सेप्टेम्बर २८ — ... ६१३ मध्ये ३१ ढलान वर्षाको सीमाभन्दा माथि थिए।
       यहाँ उद्धृत · CHIRPS daily rainfall, 613 documented slopes
    2. अगस्टमा उपग्रहको तस्बिरको १६.८% मात्र प्रयोगयोग्य थियो, र १४२ मध्ये १७ स्थान कहिल्यै देखिएन।
       यहाँ उद्धृत · Sentinel-2 scene metadata, 2,021 scenes
       [ अर्को चरण (2/6) ]

Both steps render, the grey "cited" label is right on both, and the counter advanced 1/6 to 2/6.

This is the third time this session a coordinate read off a scaled preview produced a wrong
conclusion - once as a false bug report, twice as a false "it does not work"

## The complaint, drafted on the phone

    मैले 27.81294, 85.59097 निर्देशांकको ढलानमा जोखिम देखेको छु।
    यो स्थान Melamchi, Sindhupalchok जिल्ला भित्र पर्छ।
    स्थानीय सरकार सञ्चालन ऐन, २०७४ को धारा १२(२)(ग) बमोजिम सडकसँग जोडिएको पहिरो हटाउने
    दायित्व ... को हो।
    कृपया यो स्थानको निरीक्षण गरी आवश्यक व्यवस्था मिलाउनुहुन अनुरोध गर्दछु। यो पत्र स्वचालित
    रूपमा तयार भएको हो र यसले कुनै कानुनी कारबाही सुरु गर्दैन।
    [तपाईंको नाम]  [सम्पर्क नम्बर]  [मिति]

Composed on the phone from the row, with no Python and no network: the coordinates, the district,
the office the routing key holds responsible, the section that obliges it, and a statement on the
face of the letter that it was drafted automatically and starts no proceeding. The citizen sends it
and keeps the receipt - which the app says it does not do for them.

**Still English inside the Nepali letter:** the office string itself, "Ward Committee under the Ward
Chair; municipal executive (Mayor/Chair) above it", because those descriptions live in the routing key
and are not translated. Fixing it properly means translating the duty map, not the letter - and it is
named here rather than patched in the widget, which is the mistake the beacon card taught.

## Who is responsible for the ground, on the phone

    यो जमिन कसको जिम्मामा
    Landslide at Baguwa, Melamchi Municipality-10          2.3 km
    Melamchi — Sindhupalchok
    https://www.melamchimun.gov.np/en
    Ward Committee under the Ward Chair; municipal executive (Mayor/Chair) above it
    LGOA 2074 s.12(2)(c)(23) 'Remove floods, landslides in the roads'; ...

Every complaint portal in Nepal routes to a municipality, and a municipality can say "not ours" and be
finished with it. This names the office the routing key holds responsible AND the local unit that
office belongs to, with the unit's own gov.np site, so a letter can be addressed to something that
exists rather than to "the municipality".

It says what it does not know, in the same card: the office is the routing key's DEFAULT holder for a
local road rather than a per-parcel determination, and 119 of the 613 slopes name a unit the national
gazetteer does not carry - for those it reports the office and invents no address.

The phone carries a 271 KB derived index rather than the 2.5 MB hazard record, because answering
"whose ground is this" does not need 153 days of rainfall per slope.

## Look around the valley, on the phone

    उपत्यका हेर्नुहोस्
    [ the Kathmandu valley skyline, 360 degrees, draggable ]
    यो तस्बिर होइन — उचाइको डेटाबाट बनाइएको ३६०° को चित्र हो। रूख, घर वा जमिनको रङ यसमा छैन;
    आकृति मात्र। दायाँबायाँ तान्नुहोस्।

The six panoramas are bundled into the APK, 264 KB for the whole country's walking regions, because
the places a valley view matters most are the places with no signal. Dragging left and right walks
the full 360; the aspect is 2:1 because that is what an equirectangular projection is.

And the caption refuses the obvious mistake: this is NOT a photograph. It is a silhouette from the
elevation grid the app already carries - shape, no trees, no buildings, a gradient sky.

## When to go, on the phone

The Walk tab now answers the other half of the question. Twelve bars of measured rainfall for the
nearest region, and the honesty rendered as colour rather than as a footnote:

    J 1   F 1   M 2   A 2   M 6   [J 12]  [J 26]  [A 21]  [S 13]  O 2   N 0   D 0
    grey -------- grey --------      green: cross-checked against our own CHIRPS measurement

    हरियो महिना यही परियोजनाको नापसँग जाँचिएका; खैरा केवल मोडेलको अनुमान।
    यो क्षेत्रको वर्षाको अङ्क जाँचमा उत्तीर्ण भएन — यसलाई उद्धृत नगर्नुहोस्।

That last line is Kathmandu's own failure, on the screen: ERA5 puts nearly twice the measured monsoon
there, so the app tells the user not to quote the numbers it is drawing. Twelve confident bars with a
happy summary would have been easier and would have been the exact claim this project exists to
refuse.

The trail list is below it and both work together - the season guide is additional information, never
a precondition for finding a walk.

## The frame card, translated without touching the codec

    20 बाइट · 4 बाँकी 24 मध्ये
    23373632afe320002a4a5600822d22005b15b935
    2 जना · अत्यावश्यक
    स्थान 27.71542, 85.31234
    ttl 6 · 1 पटक अगाडि बढेको
    बाइट हावामा पठाउन सक्ने एप हो यो। ब्राउजरले सक्दैन।

`peopleText` and `severity` come from the beacon codec, which the byte-parity tests share with the
JavaScript side. Localising THE CODEC to fix a caption would be the beginning of two implementations
drifting apart, so the Nepali is composed in the widget from the decoded **numbers** - `people` is an
int and the widget phrases it - and the codec stays English on both sides.

`ttl` is left as-is: it is a protocol field name, like MB, not prose.

## The screen that was half-translated

The Settings tab asked a Nepali question and answered it in English:

    यो फोनमा के चल्छ                    <- "what runs on this phone"
    vision - sees change between two images and speaks Nepali on the handset, offline
    needs ~867 MB resident, 93 MB on disk

In a Nepali-first app, on the one screen that tells a user what the model costs them. The heading was
translated, the body was two hardcoded English strings, and neither the tests nor a dozen readings of
the Dart file had noticed - because the only way to see it is to switch the app to Nepali and scroll.

Fixed, rebuilt, reinstalled and photographed:

    यो फोनमा के चल्छ
    vision - दुई तस्बिरबीचको फरक देख्छ र फोनमै नेपाली बोल्छ, इन्टरनेट बिना
    करिब 867 MB स्मृति चाहिन्छ, 93 MB डिस्कमा

The `Tier` class gained an optional `noteNe` defaulting to empty, so a tier added later without a
translation falls back to English instead of failing to compile - a missing translation is a gap to
fill, not a reason the app will not build.

## The empty screen the device exposed

The Board tab had nothing to show, because no other phone has sent anything - and until this round it
said only "there are no messages right now". On a phone, that sentence cannot be told apart from a
broken feature. It now says what the board is for and which of the two reasons applies:

    यो बोर्डले नजिकैका फोनबाट ब्लुटुथमा आएका सन्देश देखाउँछ। खाली हुनुको अर्थ दुईमध्ये एक हो:
    कसैले पठाएको छैन, वा नजिकमा अर्को फोन छैन। फोन सँगै राख्नुहोस्।

Six rounds ago I wrote the same fix for the missing trail data ("a gap in the map, not proof that
nobody walks here"). This is the same failure in a different place, and the device is what showed it.

## The 20-byte claim, as bytes on a screen

Pressing "नमुना फ्रेम बनाउनुहोस्" on the Beacon tab encodes a real advertisement and prints it:

    20 बाइट · 4 spare of 24
    233736760ee320002a4a5600822d22005b15b5ef

    2 people · critical
    position 27.71542, 85.31234
    ttl 6 · hops 1 (relayed once)

    A Flutter app can put bytes on the air. A browser cannot.

Twelve bytes of payload inside a twenty-byte frame, four bytes under the 24-byte advertisement limit
that a Bluetooth advertisement actually allows. This is the claim the whole mesh rests on, and it is
now a hex string on a phone rather than a table in a document.

The last line is the honest reason this half exists as a mobile app at all: a browser cannot put bytes
on the air, so the disaster half cannot live in the web app however hard anyone tries.

Note the aeroplane icon: the frame still encodes with no network, because encoding is computation and
not transmission - which is exactly the distinction the design turns on.

## Offline, proven with the radio actually off

The same Walk tab, with airplane mode enabled and `dumpsys connectivity` reporting
**"Active default network: none"**:

    before  131 m   675 m   343 m   84 m   2792 m   2383 m
    offline 131 m   675 m   343 m   84 m   2792 m   2383 m

Identical. The trail list is read from the 5.4 MB bundle inside the APK; nothing is fetched, nothing
is cached from a previous request, and the distances are computed on the phone. This is the claim a
whole product rests on, and it is now a screenshot with the aeroplane icon in the status bar.

## The refusal, on a device, is the best evidence in the repository

Pressing "यहाँबाट कहाँ जाने?" at Melamchi returns:

    नजिकै सुरक्षित उचाइ छैन
    "There is no safe height nearby. Within walking distance there is no ground an estimated 5 m
    higher, or that direction is not uphill. दौडन नखोज्नुहोस् - do not try to run: find a strong
    building and go to the highest floor you can. पहिले खोलाबाट टाढा जानुहोस् - first move away
    from the stream. This map is based on a grid of about 1082 metres, so treat it as regional."

The app would rather tell somebody not to run than point them at ground that is not higher. That is
the whole design, and it is now a screenshot rather than an intention.

## One thing the device showed that no test did

Every trail near Kathmandu renders as **(unnamed path)**. That is correct - OSM does not name most
urban footpaths - and the app says so instead of inventing a label. The bundle holds 979 named trails
out of 23,726, and the phone is honest about the other 22,747.
