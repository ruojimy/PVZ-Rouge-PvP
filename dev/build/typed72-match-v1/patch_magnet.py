import hashlib,json
from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
ov=root/'tools/typed72/drafts/_integration_overrides'
src=root/'build/typed72-integrated-v7/source/src/sim/typed'
def nl_of(t):return '\r\n' if '\r\n' in t else '\n'
h=(src/'service_plants.h').read_bytes().decode('utf8');nl=nl_of(h)
a='class ServicePlants {'
i=h.index(a);j=h.index('public:',i)+len('public:')
h=h[:j]+nl+'    // NativeBattle overrides __pvz_sb_GOLD_MAGNET_BUCKET_HP with balance.GOLD_MAGNET_BUCKET_HP.'+nl+'    double bucket_hp=500.;'+h[j:]
(ov/'service_plants.h').write_bytes(h.encode('utf8'))
c=(src/'service_plants.cpp').read_bytes().decode('utf8')
a='auto& b=body(t);if(!t.is_hero()){b.armor="铁桶";b.armor_hp=500.*multiplier;}'
assert c.count(a)==1
c=c.replace(a,'auto& b=body(t);if(!t.is_hero()){b.armor="铁桶";b.armor_hp=std::max(0.,std::trunc(bucket_hp*multiplier));}')
a='        if(!best||d<distance){best=MagnetTarget{t,point,false};distance=d;}'
assert c.count(a)==1
c=c.replace(a,'        if(std::getenv("MATCH_MAGNET_TRACE"))std::fprintf(stderr,"magnet t=%lld cand %s d=%.6f point=%.4f,%.4f center=%.4f,%.4f\\n",(long long)world_.heroes.tick,t.unit?t.unit->source.id.or_missing("?").c_str():"hero",d,point.x,point.y,center.x,center.y);'+nl+a)
if '#include <cstdio>' not in c:c=c.replace('#include "sim/typed/service_plants.h"','#include "sim/typed/service_plants.h"'+nl+'#include <cstdio>'+nl+'#include <cstdlib>',1)
(ov/'service_plants.cpp').write_bytes(c.encode('utf8'))
meta=ov/'OVERRIDES.json';rows=json.loads(meta.read_text(encoding='utf8'))
for n in('service_plants.h','service_plants.cpp'):
    rows[n]=dict(base='typed72-content-controller-v8 (via integrated-v7)',base_sha256=hashlib.sha256((src/n).read_bytes()).hexdigest(),
        reason='gold magnet gift uses the PvP bucket HP (balance.GOLD_MAGNET_BUCKET_HP=250, set by NativeBattle.__init__) scaled like __pvz_sb_scaled_plant_zombie_hp; MATCH_MAGNET_TRACE debug print',
        source='src/sim/pvp/gen/pm_native_battle.cpp:611, pm_original_patch1501.cpp gift_bucket_to_zombie')
meta.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8')
p=root/'build/typed72-match-v1/cold72_export.cpp';t=p.read_text(encoding='utf8')
a='{"scale_factor",parsed(pm_native_scale::FACTOR)}};'
if 'gold_magnet_bucket_hp' not in t:
    assert t.count(a)==1;t=t.replace(a,'{"scale_factor",parsed(pm_native_scale::FACTOR)},{"gold_magnet_bucket_hp",pm_balance::GOLD_MAGNET_BUCKET_HP.num()}};')
    t=t.replace('#include "sim/pvp/gen/pm_native_scale.h"\n','#include "sim/pvp/gen/pm_native_scale.h"\n#include "sim/pvp/gen/pm_balance.h"\n')
    p.write_text(t,encoding='utf8')
p=root/'build/typed72-match-v1/match_probe.cpp';t=p.read_text(encoding='utf8')
a='        collision.unit_scale=constants.at("scale_factor").get<decltype(collision.unit_scale)>();\n'
if 'bucket_hp' not in t:
    assert t.count(a)==1;t=t.replace(a,a+'        services.bucket_hp=constants.at("gold_magnet_bucket_hp");\n');p.write_text(t,encoding='utf8')
print('ok')
