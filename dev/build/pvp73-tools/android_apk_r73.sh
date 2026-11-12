#!/usr/bin/env bash
set -euo pipefail
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
cd /mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native
for d in "$HOME/pvz-android/build/dists/pvzpvp" "$HOME/pvz-native-android/dependencies/sdl2285"; do
  if [[ -d "$d/src/main/res" && -d "$d/jni/SDL/android-project" ]]; then export PVZ_ANDROID_SDL_DIST="$d"; break; fi
done
echo "dist=${PVZ_ANDROID_SDL_DIST:-none}"
export PVZ_NATIVE_RUN_ID=20261112-pvp73-r2
O=$HOME/pvz-native-android/out
export PVZ_PREVIOUS_APK="$O/PvZ-PvP-Native-1.6.0.72-typed.20261112-1112001-20261112-typed72-ai3.apk"
bash android/build_apk.sh 1112073 1.6.0.73-typed.20261112 arm64-v8a
N=$O/PvZ-PvP-Native-1.6.0.73-typed.20261112-1112073-20261112-pvp73-r2.apk
P=$O/PvZ-PvP-Native-1.6.0.72-native.20261104-1104009-20261104-humanfix-r9b-candidate.apk
BT=$HOME/pvz-android/sdk/build-tools/35.0.0
ls -la "$N"
"$BT/apksigner" verify "$N" && echo SIGNATURE_OK
a=$("$BT/apksigner" verify --print-certs "$N" | grep SHA-256); b=$("$BT/apksigner" verify --print-certs "$P" | grep SHA-256)
[[ "$a" == "$b" ]] && echo SAME_CERT_AS_RELEASE_R9B || echo CERT_DIFFERS
"$BT/aapt2" dump badging "$N" 2>/dev/null | grep -E "^package|native-code" || true
unzip -l "$N" | grep -E "libmain|libSDL2.so"
L=$HOME/pvz-native-android/candidates/$PVZ_NATIVE_RUN_ID/jniLibs/arm64-v8a/libmain.so
echo "libmain in apk vs candidate:"; unzip -p "$N" lib/arm64-v8a/libmain.so | sha256sum; sha256sum "$L"
D=/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native/dist/apk-pvp73-20261112
mkdir -p "$D"; [[ ! -e "$D/$(basename "$N")" ]]; cp "$N" "$D/"; (cd "$D"; sha256sum "$(basename "$N")" > "$(basename "$N").sha256"; cat "$(basename "$N").sha256")
