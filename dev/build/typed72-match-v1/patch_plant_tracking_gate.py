"""NativeBattle._tracking_gate (native_battle.py:712-719) is the base of g['_pvp_plant_gate']
(installed at :209; NativeContent's plant_gate calls it first, native_content.py:526-528):
    expansion.source_gate(None); periodic_targets.restore(); periodic_targets.begin(source);
    expansion.source_gate(source); cattail/tracking sources run the original target index.
The typed EntityPhase::tracking_gate already does this for entities; the plant region's
services_.plant_gate went straight to the content gate, so plants never saw targets at their
nearest periodic image (clover past half a map width), never ran the 豌豆杂交 hybrid gate
(ExpansionCombat::source_gate), and the cattail never had its target index."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'plant tracking base' in t:raise SystemExit('already patched')
a='    void zombie_gate(size_t i)override{\n'
assert t.count(a)==1
t=t.replace(a,'''    // _tracking_gate, the plant tracking base, then the content plant gate.
    void plant_gate(size_t i)override{
        const auto plant=battle.plant_roster->at(i);
        expansion.source_gate(PlantRef{});chart.restore();
        const auto source=TrackingSource::from(plant);chart.begin(source);
        expansion.source_gate(plant);
        if(plant->kind=="香蒲")chart.tracking_index(source);
        ContentPhaseProbe::plant_gate(i);
    }
'''+a)
p.write_text(t,encoding='utf8');print('ok')
