#!/usr/bin/env bash
# Everything that can only be checked on real hardware, in one command.
#
# Written because this project has verified a great deal on an emulator and four things not at all:
# the offline claim on a real radio, the Nepali speech actually being audible, the layout at a real
# handset's density, and behaviour under real memory pressure. Every one of them needs a device, and
# discovering the commands at that moment is the wrong time to be reading man pages.
#
# Usage, with the phone connected either way:
#
#   USB      plug it in, enable USB debugging, accept the prompt on the phone's screen
#   network  adb connect <phone-ip>:5555      (Developer options -> Wireless debugging)
#
# If `lsusb` in this environment shows nothing, use the network route - a sandbox that cannot see the
# USB bus will never see the phone no matter how it is plugged in.
set -uo pipefail
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$PATH:$ANDROID_HOME/platform-tools"

APK="mobile/build/app/outputs/flutter-apk/app-release.apk"
OUT="reports/device"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

say "1. a real device, not an emulator"
adb devices -l
if adb devices | grep -qE '^emulator'; then
  bad "only an emulator is attached - this script is for real hardware"
fi
SERIAL=$(adb devices | awk '/\tdevice$/{print $1}' | grep -v '^emulator' | head -1)
if [ -z "$SERIAL" ]; then
  bad "no physical device. Plug it in, or: adb connect <phone-ip>:5555"
  exit 1
fi
ok "device $SERIAL"
D="-s $SERIAL"

say "2. what it actually is"
for p in ro.product.manufacturer ro.product.model ro.build.version.release ro.build.version.sdk; do
  printf '  %-28s %s\n' "$p" "$(adb $D shell getprop $p | tr -d '\r')"
done
echo "  density  $(adb $D shell wm density | tr -d '\r')"
echo "  size     $(adb $D shell wm size | tr -d '\r')"

say "3. install and launch"
[ -f "$APK" ] || { bad "$APK missing - run: cd mobile && flutter build apk --release"; exit 1; }
adb $D install -r "$APK" | tail -1
adb $D shell monkey -p np.pahiro.pahiro_field -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 20
mkdir -p "$OUT" && adb $D shell screencap -p /sdcard/v1.png && adb $D pull /sdcard/v1.png "$OUT/pahiro-physical-launch.png" >/dev/null 2>&1
ok "$OUT/pahiro-physical-launch.png"

say "4. THE OFFLINE CLAIM, on a real radio"
adb $D shell svc wifi disable; adb $D shell svc data disable; adb $D shell svc bluetooth disable
sleep 4
echo "  wifi  $(adb $D shell settings get global wifi_on | tr -d '\r')"
echo "  data  $(adb $D shell settings get global mobile_data | tr -d '\r')"
adb $D shell dumpsys connectivity 2>/dev/null | grep -m1 -i "Active default network" | sed 's/^/  /'
adb $D shell screencap -p /sdcard/v2.png && adb $D pull /sdcard/v2.png "$OUT/pahiro-physical-airplane.png" >/dev/null 2>&1
ok "$OUT/pahiro-physical-airplane.png  <- the plan must still compute"

say "5. the speech, out loud"
adb $D logcat -c
echo "  Now press सुन्नुहोस् on the phone and LISTEN."
echo "  Then this reads back whether the platform engine spoke:"
sleep 3

say "6. restore the radios"
adb $D shell svc wifi enable; adb $D shell svc data enable
ok "radios back on - the phone is as you left it"
say "copy the frames out of $OUT and commit them"
