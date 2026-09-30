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

## What this changes, and what it does not

**Changed:** the app compiles, installs, launches, renders Nepali text, responds to touch, switches
tabs, reads its bundled trail data and lists trails by distance. Fifty rounds of "nothing has run on
a real handset" end here.

**Unchanged, and still stated everywhere:** this is an **emulator**, not a physical phone. No radio
figure has been measured on real hardware - Bluetooth range, Wi-Fi Aware range and battery endurance
are all still somebody else's measurements or modelled from them. An emulator cannot measure a radio.

## One thing the device showed that no test did

Every trail near Kathmandu renders as **(unnamed path)**. That is correct - OSM does not name most
urban footpaths - and the app says so instead of inventing a label. The bundle holds 979 named trails
out of 23,726, and the phone is honest about the other 22,747.
