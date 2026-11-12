"""native_battle._hero_damaged (native_battle.py:769-771): a damaged zombie Dave is marked for
rules["mark_seconds"]. HeroCombat::mark_seconds (hero.cpp:205) kept its default 0; only the room's
copy of the same rule was configured (long_cards_p3 t=1133)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
a='room_rules.mark_seconds=rules_json.at("mark_seconds");'
assert t.count(a)==1
if 'battle.heroes.mark_seconds=' in t:raise SystemExit('already patched')
t=t.replace(a,a+'battle.heroes.mark_seconds=room_rules.mark_seconds;')
p.write_text(t,encoding='utf8');print('ok')
