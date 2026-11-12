"""clang 14 / NDK 25 portability for the integrated typed library (arm64 build, 2026-11-08):
  * lambdas may not capture structured bindings (P1091 is clang 16+): use an explicit init-capture;
  * libc++ 14 has no <numbers>: use a constexpr double equal to std::numbers::pi (the literal rounds to
    the same double, so every computed value is bit-identical).
Takes each file from the integrated v19 stage (its current base) into _integration_overrides."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'build/typed72-integrated-v19/source/src/sim/typed'
O=Path(__file__).resolve().parent/'_integration_overrides'
PI='3.141592653589793238462643383279502884'
EDITS={
 'content_plants70.cpp':[('std::erase_if(basins,[&](const auto& item){return item.first==id;});','std::erase_if(basins,[&,id=id](const auto& item){return item.first==id;});')],
 'native_status.cpp':[('[&](const auto& item){return item.first==level;}','[&,level=level](const auto& item){return item.first==level;}')],
 'room_scheduler.cpp':[('[&](const auto& item){return item.first==key;}','[&,key=key](const auto& item){return item.first==key;}')],
}
NUMBERS=('hero_physics.cpp','world_regions.cpp','zombie_actions.cpp')
meta=O/'OVERRIDES.json';rows=json.loads(meta.read_text(encoding='utf8'))
manifest=json.loads((ROOT/'build/typed72-integrated-v19/integration-manifest.json').read_text(encoding='utf8'))['files']
for name in sorted(set(EDITS)|set(NUMBERS)):
    target=O/name;base=target if target.exists() else SRC/name
    raw=base.read_bytes();text=raw.decode('utf8')
    for a,b in EDITS.get(name,[]):
        n=text.count(a);assert n>=1,(name,a);text=text.replace(a,b)
    if name in NUMBERS:
        assert '#include <numbers>' in text,name
        text=text.replace('#include <numbers>','#include <cmath>',1)
        text=re.sub(r'std::numbers::pi\b','pvz_typed72_pi',text)
        ns=text.index('namespace pvz::typed72 {')
        text=text[:ns]+'// std::numbers::pi without <numbers> (clang 14 libc++); same double value.\nconstexpr double pvz_typed72_pi='+PI+';\n'+text[ns:]
    target.write_bytes(text.encode('utf8'))
    row=rows.setdefault(name,{})
    row.setdefault('base',manifest[name]['origin']+' (via integrated-v19)')
    row.setdefault('base_sha256',hashlib.sha256(raw).hexdigest())
    row['reason']=(row.get('reason','')+'; ' if row.get('reason') else '')+'clang 14 portability (init-capture for structured bindings; constexpr pi instead of <numbers>)'
meta.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8');print('ok')
