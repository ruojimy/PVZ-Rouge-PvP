#!/usr/bin/env bash
# Build a new self-contained PC candidate; existing packages are never replaced.
# Usage: tools/package.sh [candidate-id]
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
ID=${1:-$(date +%Y%m%d-%H%M%S)}
[[ "$ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo 'Invalid candidate id' >&2; exit 2; }
OUT="$ROOT/dist/PvZ-PvP-Native-$ID"
[[ ! -e "$OUT" ]] || { echo "Candidate already exists: $OUT" >&2; exit 2; }
CM=${PVZ_CMAKE:-/c/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe}
[[ -x "$CM" ]] || { echo 'CMake executable not found' >&2; exit 2; }
mkdir -p "$ROOT/dist/build-logs"
LOG="$ROOT/dist/build-logs/pc-$ID.log"
[[ ! -e "$LOG" ]] || { echo "Build log already exists: $LOG" >&2; exit 2; }
export _CL_="${_CL_:-} /MP1 /FS"
export CMAKE_BUILD_PARALLEL_LEVEL=1
# PVZ_BUILD_DIR: the build tree to package (default build). A new build lives in its own tree.
BUILD=${PVZ_BUILD_DIR:-build}
[[ -d "$BUILD" ]] || { echo "Build tree missing: $BUILD" >&2; exit 2; }
"$CM" --build "$BUILD" --config Release --target PvZPvPNative --parallel 1 >"$LOG" 2>&1 || {
  rc=$?; tail -n 30 "$LOG" >&2; echo "Build failed ($rc); log: $LOG" >&2; exit "$rc";
}
mkdir -p "$OUT/extract"
trap 'rc=$?; echo "Candidate incomplete ($rc), preserved at $OUT" >&2; exit "$rc"' ERR
cp "$BUILD/Release/PvZPvPNative.exe" "$BUILD"/Release/SDL2*.dll "$OUT/"
cp "$BUILD/Release/relay.json" "$OUT/relay.json"
for d in 图片 音乐 音效; do cp -R "$BUILD/Release/$d" "$OUT/"; done
cp -R extract/data extract/assets "$OUT/extract/"
cp -R fonts "$OUT/"
cp tools/启动说明.txt "$OUT/启动说明.txt"
(
  cd "$OUT"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS > "$LOG.verify"
)
printf '%s\n' "Candidate: $OUT" "Build log: $LOG"
