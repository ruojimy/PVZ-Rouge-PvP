#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native
export PVZ_NATIVE_RUN_ID=20261116-pvp743-r3
export PVZ_ANDROID_SDL_DIST="$HOME/pvz-native-android/dependencies/sdl2285"
export PVZ_PREVIOUS_APK="$PWD/dist/apk-pvp743-20261114/PvZ-PvP-Native-1.6.0.74.3-typed.20261114-1114082-20261114-pvp743-r2.apk"
candidate="$HOME/pvz-native-android/candidates/$PVZ_NATIVE_RUN_ID"
evidence="$PWD/test_results/pvp743/t24-queue-20261116/android-arm64"
[[ ! -e "$candidate" && ! -e "$evidence" ]]
mkdir -p "$candidate/prebuild-freeze" "$evidence"
cp --reflink=auto "$HOME/pvz-native-android/build-arm64-v8a/libmain.so" "$candidate/prebuild-freeze/libmain.so"
sha256sum "$candidate/prebuild-freeze/libmain.so" > "$evidence/prebuild-libmain.sha256"
python3 tools/typed72/make_app_composition.py --check
bash android/build_native.sh arm64-v8a 1
cp "$candidate/cmake-arm64-v8a.log" "$candidate/ninja-arm64-v8a.log" "$candidate/source-arm64-v8a.before.sha256" "$candidate/source-arm64-v8a.after.sha256" "$evidence/"
cp "$candidate/jniLibs/arm64-v8a/SHA256SUMS" "$evidence/"
printf '%s\n' "$candidate" > "$evidence/candidate-path.txt"
bash android/build_apk.sh 1114083 1.6.0.74.3-typed.20261114-r3 arm64-v8a
python3 test_results/pvp743/t24-queue-20261116/verify_android_package.py
printf '%s\n' 'Native ARM64 and signed APK assembled; no physical device acceptance.' > "$evidence/scope.txt"
