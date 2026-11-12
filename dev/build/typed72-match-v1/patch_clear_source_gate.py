"""native_battle.py:965, 998-1001, 1005: each entities/plants phase ends with
expansion.source_gate(None) before periodic_targets.restore(), and once more after the
wind step. The typed NativeTick calls clear_source_gate() at those three points; the
fixture only cleared source art, so PeaHybrid (豌豆杂交) kept the plant chart's row copy as
its saved index and reinstalled it later (secrets_5: zombie Dave at column 6+72)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'void clear_source_gate()override' in t:raise SystemExit('already patched')
a='    // _tracking_gate, the plant tracking base, then the content plant gate.\n'
assert t.count(a)==1
t=t.replace(a,'    void clear_source_gate()override{ContentPhaseProbe::clear_source_gate();expansion.source_gate(PlantRef{});}\n'+a)
p.write_text(t,encoding='utf8');print('ok')
