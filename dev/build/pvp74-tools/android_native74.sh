#!/usr/bin/env bash
# Android arm64-v8a native build of the frozen tree. TYPED72_STAGE is a CMake cache variable:
# point the existing build tree's cache at stage v44 first (the earlier value was a stale stage).
set -euo pipefail
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
SRC=/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native
CACHE="$HOME/pvz-native-android/build-arm64-v8a/CMakeCache.txt"
echo "before: $(grep '^TYPED72_STAGE' "$CACHE" || echo none)"
sed -i "s|^TYPED72_STAGE:PATH=.*|TYPED72_STAGE:PATH=$SRC/build/typed72-integrated-v44/source|" "$CACHE"
echo "after:  $(grep '^TYPED72_STAGE' "$CACHE")"
cd "$SRC"
export PVZ_ANDROID_SDL_DIST="$HOME/pvz-native-android/dependencies/sdl2285"
export PVZ_NATIVE_RUN_ID=20261113-pvp74-r2
start=$(date +%s)
bash android/build_native.sh arm64-v8a 1
echo "seconds=$(( $(date +%s)-start ))"
L=$HOME/pvz-native-android/candidates/$PVZ_NATIVE_RUN_ID/jniLibs/arm64-v8a/libmain.so
echo "typed session string: $(strings "$L" | grep -c 'typed72] battle session started')"
echo "backend_audit string: $(strings "$L" | grep -c 'backend_audit')"
sha256sum "$L"
