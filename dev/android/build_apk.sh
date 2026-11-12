#!/usr/bin/env bash
# WSL: assemble/sign a new APK from an explicit, verified native candidate.
# Usage: PVZ_NATIVE_RUN_ID=<run> bash android/build_apk.sh <code> <name> <abi> [abi...]
set -euo pipefail
[[ $# -ge 3 ]] || { echo 'Expected versionCode versionName and at least one ABI' >&2; exit 2; }
VCODE=$1; VNAME=$2; shift 2; ABIS=("$@")
[[ "$VCODE" =~ ^[1-9][0-9]*$ && "$VNAME" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo 'Invalid version' >&2; exit 2; }
RUN=${PVZ_NATIVE_RUN_ID:?Set PVZ_NATIVE_RUN_ID to the explicit native build candidate}
[[ "$RUN" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo 'Invalid native run id' >&2; exit 2; }
SRC=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
STAGING=${PVZ_ANDROID_ASSET_STAGING:-/mnt/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/dist/android-pvp71-staging}
SDK=${PVZ_ANDROID_SDK:-$HOME/pvz-android/sdk}
DIST=${PVZ_ANDROID_SDL_DIST:-$HOME/pvz-android/build/dists/pvzpvp}
WORK=${PVZ_ANDROID_WORK:-$HOME/pvz-native-android}
NATIVE="$WORK/candidates/$RUN"
BT="$SDK/build-tools/35.0.0"
export GRADLE_USER_HOME="$HOME/pvz-android/gradle-home"
GRADLE=${PVZ_ANDROID_GRADLE:-$HOME/pvz-android/gradle/bin/gradle}
[[ -d "$NATIVE" ]] || { echo "Native candidate does not exist: $NATIVE" >&2; exit 2; }
declare -A SEEN_ABIS=()
for abi in "${ABIS[@]}"; do
  [[ -z "${SEEN_ABIS[$abi]:-}" ]] || { echo "Duplicate ABI: $abi" >&2; exit 2; }
  SEEN_ABIS[$abi]=1
done
CURRENT=$(mktemp "$NATIVE/apk-source-XXXXXXXX.sha256")
(cd "$SRC"; find src android extract/data extract/schema tools/pvp72_sources -type f ! -path '*/__pycache__/*' ! -path 'src/uitools/*' ! -path 'src/cpptests/*' ! -path 'src/tools/*' ! -path 'src/sim/pvp/shim_headless/*' -print0 | sort -z | xargs -0 sha256sum) > "$CURRENT"
for abi in "${ABIS[@]}"; do
  [[ "$abi" == arm64-v8a || "$abi" == x86_64 ]] || { echo 'Unsupported ABI' >&2; exit 2; }
  [[ -f "$NATIVE/jniLibs/$abi/libmain.so" && -f "$NATIVE/jniLibs/$abi/SHA256SUMS" ]] || { echo "Missing verified native candidate for $abi" >&2; exit 2; }
  (cd "$NATIVE/jniLibs/$abi"; sha256sum -c SHA256SUMS)
  cmp "$CURRENT" "$NATIVE/source-$abi.after.sha256"
done
mkdir -p "$WORK/out"
OUTAPK="$WORK/out/PvZ-PvP-Native-$VNAME-$VCODE-$RUN.apk"
[[ ! -e "$OUTAPK" ]] || { echo "APK already exists: $OUTAPK" >&2; exit 2; }
ASSEMBLY=$(mktemp -d "$NATIVE/apk-$VCODE-XXXXXXXX")
A="$ASSEMBLY/assets"; P="$ASSEMBLY/app"
mkdir -p "$A/extract" "$A/fonts" "$P" "$ASSEMBLY/jniLibs"
for abi in "${ABIS[@]}"; do cp -R "$NATIVE/jniLibs/$abi" "$ASSEMBLY/jniLibs/"; done
cp -R "$SRC/extract/data" "$SRC/extract/assets" "$A/extract/"
for d in 图片 音乐 音效; do cp -R "$SRC/build/Release/$d" "$A/"; done
cp "$SRC/build/Release/relay.json" "$A/relay.json"
cp "$STAGING/fonts/cjk.ttf" "$A/fonts/cjk.ttf"
cp "$SRC/fonts/"* "$A/fonts/"
(cd "$A"; { printf '%s\n' "$VNAME-$VCODE-$RUN"; find . -type f ! -name manifest.txt | sed 's|^\./||' | sort; } > manifest.txt)
cp -R "$SRC/android/project/." "$P/"
cp -R "$DIST/src/main/res/"drawable* "$P/res/"
python3 "$SRC/android/prepare_sdl_java.py" \
  --source "$DIST/jni/SDL/android-project/app/src/main/java" \
  --output "$ASSEMBLY/sdl-java" --report "$ASSEMBLY/sdl-java-patches.json" \
  --patch "$ASSEMBLY/sdl-java-backport.patch"
abilist=$(printf "'%s', " "${ABIS[@]}"); abilist=${abilist%, }
sed -i "s|@VERSION_CODE@|$VCODE|; s|@VERSION_NAME@|$VNAME|; s|@ABIS@|$abilist|; s|@WORK@|$ASSEMBLY|g; s|@SDLJAVA@|$ASSEMBLY/sdl-java|" "$P/build.gradle"
printf 'sdk.dir=%s\n' "$SDK" > "$P/local.properties"
printf 'org.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8\norg.gradle.console=plain\norg.gradle.workers.max=1\nandroid.useAndroidX=false\n' > "$P/gradle.properties"
printf "rootProject.name = 'pvzpvpnative'\n" > "$P/settings.gradle"
(cd "$P"; "$GRADLE" --offline --no-daemon --max-workers=1 -q assembleRelease) > "$ASSEMBLY/gradle.log" 2>&1 || {
  rc=$?; tail -n 30 "$ASSEMBLY/gradle.log" >&2; exit "$rc";
}
mapfile -t APKS < <(find "$P/build/outputs/apk/release" -maxdepth 1 -type f -name '*.apk')
[[ ${#APKS[@]} == 1 ]] || { echo 'Expected exactly one release APK' >&2; exit 1; }
"$BT/zipalign" -P 16 4 "${APKS[0]}" "$ASSEMBLY/aligned.apk"
set -a; source "$HOME/pvz-android/keystore.env"; set +a
"$BT/apksigner" sign --ks "$HOME/pvz-android/pvzpvp.keystore" --ks-key-alias "$PVP_KEYALIAS" \
  --ks-pass env:PVP_KEYSTORE_PW --key-pass env:PVP_KEYALIAS_PW --out "$OUTAPK" "$ASSEMBLY/aligned.apk"
unset PVP_KEYSTORE_PW PVP_KEYALIAS_PW
"$BT/apksigner" verify --verbose "$OUTAPK" > "$ASSEMBLY/signature.log"
"$BT/apksigner" verify --print-certs "$OUTAPK" > "$ASSEMBLY/certificate.txt"
PREVIOUS_APK=${PVZ_PREVIOUS_APK:?Set PVZ_PREVIOUS_APK to the current signed APK for upgrade continuity verification}
[[ -f "$PREVIOUS_APK" ]] || { echo 'Previous native APK required for certificate continuity verification' >&2; exit 2; }
"$BT/apksigner" verify --print-certs "$PREVIOUS_APK" > "$ASSEMBLY/previous-certificate.txt"
diff <(sed -n '/certificate SHA-256 digest:/p' "$ASSEMBLY/previous-certificate.txt") <(sed -n '/certificate SHA-256 digest:/p' "$ASSEMBLY/certificate.txt")
"$BT/aapt" dump badging "$PREVIOUS_APK" > "$ASSEMBLY/previous-badging.txt"
"$BT/aapt" dump badging "$OUTAPK" > "$ASSEMBLY/badging.txt"
# Anchor name to the package field; an unanchored .*name also matches the
# trailing compileSdkVersionCodename and misreads a valid package as "15".
OLD_PACKAGE=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$ASSEMBLY/previous-badging.txt")
NEW_PACKAGE=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$ASSEMBLY/badging.txt")
OLD_CODE=$(sed -n "s/^package:.* versionCode='\([0-9]*\)'.*/\1/p" "$ASSEMBLY/previous-badging.txt")
NEW_CODE=$(sed -n "s/^package:.* versionCode='\([0-9]*\)'.*/\1/p" "$ASSEMBLY/badging.txt")
[[ "$OLD_PACKAGE" == org.pvzrouge.pvzpvpnative && "$NEW_PACKAGE" == "$OLD_PACKAGE" ]] || { echo 'Package identity differs' >&2; exit 2; }
[[ "$OLD_CODE" =~ ^[0-9]+$ && "$NEW_CODE" == "$VCODE" ]] || { echo 'Invalid package versionCode' >&2; exit 2; }
(( 10#$NEW_CODE > 10#$OLD_CODE )) || { echo 'Upgrade versionCode must increase' >&2; exit 2; }
sha256sum "$OUTAPK" > "$OUTAPK.sha256"
printf '%s\n' "Signed candidate: $OUTAPK" "Evidence: $ASSEMBLY"
