#!/usr/bin/env bash
# WSL: build one ABI serially into a new versioned candidate.
# PVZ_NATIVE_RUN_ID can group ABI builds; existing ABI outputs are never replaced.
set -euo pipefail
ABI=${1:-arm64-v8a}
JOBS=${2:-1}
[[ "$ABI" == arm64-v8a || "$ABI" == x86_64 ]] || { echo 'Unsupported ABI' >&2; exit 2; }
[[ "$JOBS" == 1 ]] || { echo 'This workspace requires a single compiler job' >&2; exit 2; }
SRC=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
NDK=${PVZ_ANDROID_NDK:-$HOME/pvz-android/sdk/ndk/25.1.8937393}
DIST=${PVZ_ANDROID_SDL_DIST:-$HOME/pvz-android/build/dists/pvzpvp}
WORK=${PVZ_ANDROID_WORK:-$HOME/pvz-native-android}
RUN=${PVZ_NATIVE_RUN_ID:-$(date +%Y%m%d-%H%M%S)}
[[ "$RUN" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo 'Invalid native run id' >&2; exit 2; }
CANDIDATE="$WORK/candidates/$RUN"
ABIROOT="$CANDIDATE/jniLibs/$ABI"
[[ ! -e "$ABIROOT" ]] || { echo "ABI candidate exists: $ABIROOT" >&2; exit 2; }
[[ -f "$NDK/build/cmake/android.toolchain.cmake" ]] || { echo 'Android NDK missing' >&2; exit 2; }
mkdir -p "$CANDIDATE/jniLibs" "$WORK/build-$ABI"
fingerprint() { (cd "$SRC"; find src android extract/data extract/schema tools/pvp72_sources -type f ! -path '*/__pycache__/*' ! -path 'src/uitools/*' ! -path 'src/cpptests/*' ! -path 'src/tools/*' ! -path 'src/sim/pvp/shim_headless/*' -print0 | sort -z | xargs -0 sha256sum); }
fingerprint > "$CANDIDATE/source-$ABI.before.sha256"
mkdir "$ABIROOT"
cp "$DIST/libs/$ABI/"libSDL2*.so "$ABIROOT/"
cmake -S "$SRC/android" -B "$WORK/build-$ABI" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI="$ABI" -DANDROID_PLATFORM=android-23 -DANDROID_STL=c++_static \
  -DCMAKE_BUILD_TYPE=Release -DSDL_JNI="$DIST/jni" -DSDL_LIBDIR="$ABIROOT" \
  > "$CANDIDATE/cmake-$ABI.log" 2>&1
cmake --build "$WORK/build-$ABI" --parallel 1 > "$CANDIDATE/ninja-$ABI.log" 2>&1 || {
  rc=$?; tail -n 40 "$CANDIDATE/ninja-$ABI.log" >&2; exit "$rc";
}
fingerprint > "$CANDIDATE/source-$ABI.after.sha256"
cmp "$CANDIDATE/source-$ABI.before.sha256" "$CANDIDATE/source-$ABI.after.sha256"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" --strip-unneeded \
  -o "$ABIROOT/libmain.so" "$WORK/build-$ABI/libmain.so"
(cd "$ABIROOT"; sha256sum ./*.so > SHA256SUMS; sha256sum -c SHA256SUMS)
printf '%s\n' "Native candidate: $CANDIDATE" "PVZ_NATIVE_RUN_ID=$RUN"
