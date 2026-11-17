#!/bin/bash
# CI smoke test on the ARCore emulator: does the app open, and does the walk screen (AR + Poppy + trail) run without
# crashing? Screenshots and the crash log (if any) go to smoke/.
set -x
mkdir -p smoke
alive() { timeout 12 adb shell true > /dev/null 2>&1; }
log() { timeout 60 adb logcat -d -s FollowPoppy:I PoppySmoke:I AndroidRuntime:E libc:F DEBUG:F filament:E gltfio:E Filament:E > "$1" 2>&1; }
gone() { [ -z "$(timeout 10 adb shell pidof app.followpoppy)" ]; }
URL=$(gh api repos/google-ar/arcore-android-sdk/releases/latest -q '.assets[] | select(.name | test("x86_for_emulator")) | .browser_download_url' | head -1)
echo "ARCore: $URL" > smoke/summary.txt
curl -fsSL -o /tmp/arcore.apk "$URL" && adb install -r /tmp/arcore.apk >> smoke/summary.txt 2>&1
adb install -r -g app-debug.apk >> smoke/summary.txt 2>&1

echo "--- opening (splash, then boy or girl) ---" >> smoke/summary.txt
timeout 20 adb logcat -c
timeout 30 adb shell am start -n app.followpoppy/.MainActivity
sleep 1.5; timeout 25 adb exec-out screencap -p > smoke/1_splash.png
sleep 4; timeout 25 adb exec-out screencap -p > smoke/2_choose.png
log smoke/open_log.txt
if gone; then echo "CRASHED on opening" >> smoke/summary.txt; else echo "opening ok" >> smoke/summary.txt; fi
grep -E "FATAL|Exception|Abort|signal" smoke/open_log.txt | head -20 >> smoke/summary.txt
timeout 20 adb shell am force-stop app.followpoppy; sleep 2

echo "--- walk screen (Tel Aviv) ---" >> smoke/summary.txt
timeout 20 adb logcat -c
timeout 30 adb shell am start -n app.followpoppy/.MainActivity --ez smoke true --es dest "32.0853,34.7818" --es from "32.0868,34.7797"
for n in $(seq 1 12); do
  sleep 5; alive || { echo "emulator stopped answering" >> smoke/summary.txt; break; }
  [ $n = 4 ] && timeout 25 adb exec-out screencap -p > smoke/3_walk.png
  if gone; then echo "CRASHED on the walk screen after $((n*5)) s" >> smoke/summary.txt; break; fi
done
gone || echo "walk screen ok (60 s)" >> smoke/summary.txt
timeout 25 adb exec-out screencap -p > smoke/4_walk_end.png
log smoke/walk_log.txt
grep -vE "^\s+at " smoke/walk_log.txt | grep -iE "FATAL|Exception|Abort|signal|backtrace|#0[0-9] pc|route|session|poppy rig|ribbon|streetscape|error" | cut -c1-300 | head -60 >> smoke/summary.txt
timeout 20 adb shell am force-stop app.followpoppy
exit 0
