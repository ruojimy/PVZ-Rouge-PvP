#!/usr/bin/env bash
# Serial rebuild. "gen" stages translations for review without removing live sources.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
CM=${PVZ_CMAKE:-/c/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe}
export _CL_="${_CL_:-} /MP1 /FS"
export CMAKE_BUILD_PARALLEL_LEVEL=1
if [[ "${1:-}" == gen ]]; then
  P=${PVZ_GENERATOR_PYTHON:-/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe}
  STAGE=$(mktemp -d "$ROOT/build/regeneration-XXXXXXXX")
  mapfile -t MODS < <(tr -s '[:space:]' '\n' < tools/sim_modules.txt)
  "$P" tools/pvp2cpp.py "$STAGE/sim/pvp/gen" "${MODS[@]}" > "$STAGE/generation.log" 2>&1 || {
    rc=$?; tail -n 30 "$STAGE/generation.log" >&2; exit "$rc";
  }
  printf '%s\n' "Translations staged at $STAGE; live generated sources were not replaced."
  exit 0
fi
[[ $# == 0 ]] || { echo 'Usage: tools/rebuild.sh [gen]' >&2; exit 2; }
"$CM" --build build --config Release --target run_battle --parallel 1
