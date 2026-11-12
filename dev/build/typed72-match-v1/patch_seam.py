"""Integration overrides: fixes applied to the file version the integrated tree really uses.

tools/typed72/drafts/_integration_overrides/<name> replaces the merged file last;
each override records its base origin and SHA in OVERRIDES.json.
"""
import hashlib,json
from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
ov=root/'tools/typed72/drafts/_integration_overrides';ov.mkdir(exist_ok=True)
base=root/'build/typed72-integrated-v7/source/src/sim/typed/zombie_pea.cpp'
t=base.read_bytes().decode('utf8')
nl='\r\n' if '\r\n' in t else '\n'
a='void ZombiePeas::torch_check(const EntityRef& e) {'+nl;assert t.count(a)==1
# native_projectiles._install_zombie_pea_seam (PvP72 hand-written): before the torch
# check and the hit test, re-express prev_x next to x so a seam crossing never spans the map.
seam=('namespace {'+nl+'void seam(TypedBattleState& world,const EntityRef& e){'+nl+
      '    auto& previous=e->pea.previous_x;if(!previous.present()||previous.is_null()||!world.world_width.present())return;'+nl+
      '    const double x=e->motion.get().x;previous.set(x+wrap_delta(x,previous.get(),world.world_width.get()));'+nl+'}'+nl+'}'+nl)
t=t.replace(a,seam+a+'    seam(world_,e);'+nl)
a='bool ZombiePeas::hit(const EntityRef& e){';assert t.count(a)==1
t=t.replace(a,a+'seam(world_,e);')
if '#include "sim/typed/projectile_rules.h"' not in t:t=t.replace('#include "sim/typed/zombie_pea.h"','#include "sim/typed/zombie_pea.h"'+nl+'#include "sim/typed/projectile_rules.h"',1)
(ov/'zombie_pea.cpp').write_bytes(t.encode('utf8'))
meta=ov/'OVERRIDES.json';rows=json.loads(meta.read_text(encoding='utf8')) if meta.exists() else {}
rows['zombie_pea.cpp']=dict(base='typed72-content-controller-v8 (via integrated-v7)',base_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),
    reason='port native_projectiles._install_zombie_pea_seam: prev_x re-expressed next to x before torch_check and hit',source='modkit/pvp/native_projectiles.py:46-61')
meta.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8')
p=root/'tools/typed72/integrate_stage.py';s=p.read_text(encoding='utf8')
a="    # Additive authoritative fields from sibling stages.\n"
if 'OVERRIDES' not in s:
    assert s.count(a)==1
    s=s.replace(a,"""    # Fixes to the exact file version used here; see _integration_overrides/OVERRIDES.json.
    overrides=DRAFT/'_integration_overrides'
    if overrides.exists():
        for path in sorted(overrides.iterdir()):
            if path.is_file() and is_source(path):shutil.copyfile(path,source/path.name);origin[path.name]=('integration-override',sha(path))
"""+a)
    p.write_text(s,encoding='utf8')
print('ok')
