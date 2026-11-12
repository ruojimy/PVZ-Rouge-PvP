#!/bin/bash
# Run every oracle scenario in C++ and diff against the Python recordings (extract/oracle/<name>.jsonl).
#   tools/check_all.sh [names...]     (default: core scenarios + all cards_* / secrets_* batches)
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
P=/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe
CORE="empty basic zombie_swarm projectile_storm mixed_late_game hero_inputs grave_economy duo_basic coop_waves"
CARDS=$(ls tools/scenarios/ | grep -E "^(cards|secrets)_.*[.]json$" | sed "s/[.]json$//" | xargs)
failed=0
for s in ${@:-$CORE $CARDS}; do
  f=tools/scenarios/_expanded_$s.json; [ -f $f ] || f=tools/scenarios/$s.json
  rm -f extract/oracle_cpp/$s.jsonl
  timeout 900 ./build/Release/run_battle.exe $f extract/oracle_cpp/$s.jsonl > extract/oracle_cpp/$s.run.log 2>&1 || { printf "%-18s C++ RUN FAILED (extract/oracle_cpp/%s.run.log)\n" $s $s; failed=1; continue; }
  diff_output=$(PYTHONIOENCODING=utf-8 $P tools/oracle_diff.py $s --max 3 2>&1)
  diff_rc=$?
  printf "%-18s %s\n" "$s" "$(printf '%s\n' "$diff_output" | tail -1 | cut -c1-160)"
  if [ "$diff_rc" != 0 ]; then failed=1; fi
done

exit "$failed"
