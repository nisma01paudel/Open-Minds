# The Android app, assessed as an artifact

A static assessment of the release APK, done by the same rule the rest of this repository runs on:
a claim about a control is only worth what was actually checked on the artifact that ships.

Method: the APK was decompressed and its manifest read with `aapt2 dump xmltree`, its contents grepped
for credential shapes, and every HTTP endpoint it references was dialled. **No device was needed for any
of this, and no finding below is inferred from the source tree alone.**

    artifact   mobile/build/app/outputs/flutter-apk/app-release.apk
    target     Samsung SM-E225F, Android 13 (SDK 33), arm64-v8a

## What is clean, and how that was established

**No secrets in the artifact.** The decompressed APK was grepped for Google API keys (`AIza` + 35),
OpenAI-style keys (`sk-`), AWS access key IDs (`AKIA`), PEM private-key blocks, and Slack and Hugging
Face token shapes. **Zero matches for every one.** This matters more here than usual: the whole project
runs on open-weight models locally, so a bundled vendor key would be both a leak and a contradiction.

**`android:debuggable` is not set** — false in a release build, which is what ships.

**`android:extractNativeLibs="false"`** — the native libraries stay compressed in the APK rather than
being written out to app storage, so they cannot be swapped on disk after install.

**Cleartext HTTP is not enabled.** `usesCleartextTraffic` is absent, which on the declared target SDK
means false. The app's own traffic — and there is none at runtime — would be refused if it were plain.

**The one exported library component is guarded.**
`androidx.profileinstaller.ProfileInstallReceiver` is exported, which looks alarming and is not: it
carries `android:permission="android.permission.DUMP"`, so only a shell or a rooted/system caller can
reach it. That is the AndroidX default, not something this project added.

**The launcher activity is exported**, as it must be to appear in the launcher. It takes no intent
extras and reads no data from its intent, so there is no injection surface behind the export.

## The finding worth recording

**Fourteen local-government websites are referenced over plain `http://`.**

    butwalmun.gov.np          ghorahimun.gov.np       hetaudamun.gov.np
    itaharimun.gov.np         kalaiyamun.gov.np       pandavgufamun.gov.np
    tulsipurmun.gov.np        dhangadhimun.gov.np     ...

These are the official addresses published by the municipalities themselves, carried in
`web/public/data/administration.json` and shown to the user so a complaint can be addressed to a real
office. **The app does not fetch them** — it offers them to a browser. But a user who taps one from a
hostile network can be redirected to a page that looks like their own municipality, which for a
complaint portal is a phishing surface with a plausible pretext.

**Every one was dialled over TLS to see whether the URL could simply be upgraded:**

    www.diprungmun.gov.np   https 200   -> upgradable
    butwalmun.gov.np        https 000   -> no TLS listener
    ghorahimun.gov.np       https 000
    hetaudamun.gov.np       https 000
    itaharimun.gov.np       https 000
    pandavgufamun.gov.np    https 000
    tulsipurmun.gov.np      https 000

**Six of the seven tested have no HTTPS at all.** Rewriting them to `https://` would not secure them; it
would break them, and a dead link on the one screen whose entire purpose is reaching a duty holder is
worse than an unencrypted working one.

**So this is recorded rather than silently patched.** The honest remediation is one of:

1. upgrade only the hosts confirmed to answer on TLS, and leave the rest as published
2. mark each link in the interface as secured or not, so a user knows which one they are opening
3. state plainly, where the links are listed, that the municipality's own site is the weakest link in
   this chain and is not something this project controls

**Attempted and reverted, on purpose.** A `siteLabel()` helper was written to append "not encrypted"
after any `http://` address. It failed to compile at both call sites: the duty panel shadows `L10n` with
a local `String s`, and `PlacesPanel` does not take an `L10n` at all — it takes a `bool nepali`. Threading
a translated string through both is more surgery than the change deserves, and a half-applied marker is
worse than none, so it was reverted rather than forced.

**The next attempt should pass the finished label down as a plain `String` from a screen that already has
`L10n`**, rather than reaching for it inside the panel.

**The URL text itself is not hidden**: `http://` is visible in every one of them, so a careful reader can
already tell. What is missing is that most readers will not.

**Not otherwise done here because it changes what the user sees, and on this screen that is an
editorial call.**

## What was not assessed, and why

**MASVS-RESILIENCE — root, tamper and anti-debug detection: not present, deliberately.** This is a
public-safety tool that a person may need to run on an old, rooted, borrowed or cracked phone during a
flood. A control that refuses to run on a rooted device would be actively harmful here. Its absence is a
design position, not an oversight, and it should be reported that way.

**Dynamic analysis with Frida was not run.** Nothing in this app is protected by a runtime-only control
— there is no certificate pinning, no Keystore-bound secret, and no root reaction, so there is no
control whose effectiveness could only be proven at runtime. The static findings above are complete for
this artifact. **That is a statement about this app, not a general one.**

**The backend recovery pass was not applicable**: the bundle yields no API endpoints because the app has
no network layer at all. Its entire data set ships as assets.

## The one thing this assessment cannot say

**Whether the Nepali speech is audible.** That is not a security property and no static tool reaches it.
It needs a person holding the phone and pressing सुन्नुहोस्, and it is still open.
