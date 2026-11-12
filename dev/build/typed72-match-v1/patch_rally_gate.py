"""NativeBattle._rally_zombie_gate (native_battle.py:1525, installed as g['_pvp_zombie_gate'] at :258)
restores the rally base and swaps in the unit's rally path field, then calls _native_zombie_gate,
the ordinary content/expansion/September/PvP56/PvP64 gate chain (:2624 refs). The typed
SeatPathTracking::select_rally is that first half; the composition never called it."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
a='    void zombie_gate(size_t i)override{ContentPhaseProbe::zombie_gate(i);expansion.zombie_gate(battle.targets->at(i).unit);}'
assert t.count(a)==1
t=t.replace(a,'    void zombie_gate(size_t i)override{\n        if(const auto& unit=battle.targets->at(i).unit)path_banks.select_rally(*unit);\n        ContentPhaseProbe::zombie_gate(i);expansion.zombie_gate(battle.targets->at(i).unit);\n    }')
p.write_text(t,encoding='utf8');print('ok')
