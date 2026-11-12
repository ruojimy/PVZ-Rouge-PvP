#!/bin/bash
# Build app_run and run python's scripted UI smoke; print swallowed/fatal errors.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
CM="/c/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
"$CM" --build build --config Release --target app_run 2>&1 | grep -E " error " | sed 's/.*src/src/' | cut -c1-200 | head -5
L=${TMP:-/tmp}/pvz_smoke.log
PVZ_TRACE=1 timeout ${1:-600} ./build/Release/app_run.exe smoke ${2:-smoke.png} > $L 2>&1
echo "exit $?"
grep "^---- PyError" $L | sort | uniq -c | sort -rn | head -12
tail -2 $L | cut -c1-300
