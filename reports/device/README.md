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

## What this changes, and what it does not

**Changed:** the app compiles, installs, launches, renders Nepali text, responds to touch, switches
tabs, reads its bundled trail data and lists trails by distance. Fifty rounds of "nothing has run on
a real handset" end here.

**Unchanged, and still stated everywhere:** this is an **emulator**, not a physical phone. No radio
figure has been measured on real hardware - Bluetooth range, Wi-Fi Aware range and battery endurance
are all still somebody else's measurements or modelled from them. An emulator cannot measure a radio.

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
