#!/bin/bash
# Native integration scenarios plus the migrated legacy unittest suite.
# The integration scenarios alone are not full legacy-suite acceptance.
#   tools/full_test.sh [out_dir]      -> <out_dir>/report.txt (default: test_results/<timestamp>)
#   FULL_SKIP_RELAY=1 skips the public-relay test (it talks to the relay in relay.json).
set -u
set -o pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
P=/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe
CM="/c/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
OUT=${1:-test_results/$(date +%Y%m%d-%H%M%S)}
if [ -e "$OUT/report.txt" ] || compgen -G "$OUT/*.result" > /dev/null; then
  echo "Refusing to reuse existing test results: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd); OW=$(cygpath -w "$OUT")
echo "== build" | tee "$OUT/report.txt"
export _CL_="${_CL_:-} /MP1 /FS"
export CMAKE_BUILD_PARALLEL_LEVEL=1
if ! "$CM" --build build --config Release --parallel 1 > "$OUT/build.log" 2>&1; then
  echo "FAIL build (see build.log)" | tee -a "$OUT/report.txt"
  exit 1
fi
APP=./build/Release/app_run.exe

ud() { mkdir -p "$OUT/ud/$1"; echo "$OW\\ud\\$1"; }
run() {   # run <name> <timeout> <pass-grep> cmd...
  local name=$1 to=$2 pat=$3; shift 3
  ( PVP_USERDATA=$(ud $name) timeout $to "$@" > "$OUT/$name.log" 2>&1; rc=$?; echo "exit $rc" >> "$OUT/$name.log"
    if [ "$rc" = 0 ] && grep -qE "$pat" "$OUT/$name.log"; then echo "PASS $name" > "$OUT/$name.result"; else echo "FAIL $name (see $name.log)" > "$OUT/$name.result"; fi )
}
# Only the peers of one network scenario need simultaneous processes.
run_bg() { run "$@" & }

# kernel oracle (34 scenarios) first: it uses run_battle.exe only
( tools/check_all.sh > "$OUT/check_all.log" 2>&1
  rc=$?
  n=$(grep -c IDENTICAL "$OUT/check_all.log"); [ "$rc" = 0 ] && [ "$n" = 34 ] && echo "PASS check_all (34/34 IDENTICAL)" > "$OUT/check_all.result" || echo "FAIL check_all ($n/34, exit $rc)" > "$OUT/check_all.result" )

# UI / local
run smoke     900  "PVZ_NATIVE_SMOKE_PASSED"   $APP smoke "$OW\\smoke.png"
mkdir -p "$OUT/evidence"
run evidence  1500 "replay_checks_passed|PVZ_NATIVE_SMOKE_PASSED" $APP evidence "$OW\\evidence\\report.json"
run almanac   600  "ALMANAC 232 cards"          $APP almanac
run probe     300  "PROBE frame=160 fullscreen=false" $APP probe
mkdir -p "$OUT/map" "$OUT/coop"
run mapedit   300  "PASS draft on the custom map" $APP mapedit "$OW\\map"
run cooplobby 600  "PASS teammate planted"       $APP cooplobby "$OW\\coop"
run airoom    900  "AI DONE"                     $APP airoom 30
wait

# regex conformance against real python
$P tools/re_cases.py gen "$OW\\re_cases.json" > /dev/null
if $APP retest "$OW\\re_cases.json" "$OW\\re_native.json" > "$OUT/regex-native.log" 2>&1 && PYTHONIOENCODING=utf-8 $P tools/re_cases.py diff "$OW\\re_cases.json" "$OW\\re_native.json" > "$OUT/regex.log" 2>&1; then echo "PASS regex ($(tail -1 $OUT/regex.log))" > "$OUT/regex.result"; else echo "FAIL regex (see regex logs)" > "$OUT/regex.result"; fi

# network
run nettest 120 "NETTEST .*PASS" $APP nettest
wait
rm -f "$OUT/tok1.txt" "$OUT/tok2.txt" "$OUT/tok3.txt"
run_bg net_host  400 "REPLAY verified=true"       $APP netpeer host 47191 "$OW\\tok1.txt" duel
sleep 3
run_bg net_spec  400 "spectate PASS"              $APP netpeer spectate 47191 "$OW\\tok1.txt" duel
sleep 1
run_bg net_guest 400 "guest PASS battle reached"  $APP netpeer guest 47191 "$OW\\tok1.txt" duel
wait
run_bg coop_host 200 "host CHAT OK"               $APP netpeer host 47192 "$OW\\tok2.txt" coop
sleep 3
run_bg coop_guest 200 "guest CHAT OK"             $APP netpeer guest 47192 "$OW\\tok2.txt" coop
wait
if [ -z "${FULL_SKIP_RELAY:-}" ]; then
  run_bg relay_host 400 "host PASS battle reached"           $APP netpeer host 0 "$OW\\tok3.txt" relay
  sleep 2
  run_bg relay_guest 400 "guest frame=[0-9]+ t=[0-9]+ phase=battle" $APP netpeer guest 0 "$OW\\tok3.txt" relay
  wait
fi

if $P tools/run_cpp_suite.py --out "$OW\\legacy-suite" --workers auto --timeout 600 > "$OUT/legacy-suite.log" 2>&1; then
  echo "PASS legacy-suite (temporary exact waivers enabled; raw counts in legacy-suite/summary.json)" > "$OUT/legacy-suite.result"
else
  echo "FAIL legacy-suite (see legacy-suite/summary.json and collection-mismatch.json)" > "$OUT/legacy-suite.result"
fi

echo "== results" | tee -a "$OUT/report.txt"
cat "$OUT"/*.result | sort | tee -a "$OUT/report.txt"
pass=$(cat "$OUT"/*.result | grep -c ^PASS); total=$(cat "$OUT"/*.result | wc -l)
echo "TOTAL $pass/$total passed  ($OUT)" | tee -a "$OUT/report.txt"
[ "$pass" = "$total" ]
