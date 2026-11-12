#!/bin/bash
# Minimum of N runs of the C++ bench (machine noise is large): tools/bench.sh [scenario] [runs]
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
s=${1:-mixed_late_game}; n=${2:-6}
f=tools/scenarios/_expanded_$s.json; [ -f $f ] || f=tools/scenarios/$s.json
for i in $(seq $n); do ./build/Release/run_battle.exe $f --bench; done | sed 's/.*ticks //; s/s$//' | sort -n | head -1 | sed "s/^/$s min: /; s/$/s/"
