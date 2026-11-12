"""Freeze the effective PvP plant-zombie constants into fixed C++ fields."""
import argparse
import copy
import json
import marshal
import random
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import proxy_reference
from verify_stages import sha

NUMBERS=('hp','burst','burst_gap','cooldown','initial_cooldown_max','fire_anim','head_scale','head_x','head_y',
    'duck_head_x','duck_head_y','armor_x','armor_y','knockback','move_speed','jump_speed','plant_damage',
    'visual_tick','damage_tick','damage_pulses','range_tiles','attack_length','visual_bubbles','radius')
FLAGS=('shoot','doom','blover','lantern','squash','gravebuster','umbrella','gold_magnet','fumeshroom')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--evidence',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);evidence=Path(a.evidence).resolve();evidence.mkdir(parents=True,exist_ok=False)
    raw=proxy_reference.REF/'reverse_engineered/raw/pvzrouge.pyc';code=marshal.loads(raw.read_bytes())
    functions={c.co_name:c for c in code.co_consts if isinstance(c,types.CodeType)};rng=random.Random(1)
    g=dict(random=rng,随=rng.randint,c=copy.deepcopy,僵尸=[],实体=[],模式='正常模式',玩家位置=[0.,0.,0.,0.],比=48.,plk=.0048)
    patch=proxy_reference.install(g,functions);configs=patch.ns['__pvz_sb_PLANT_ZOMBIE_CONFIG']
    allowed={'head'}|set(NUMBERS)|set(FLAGS)
    for kind,config in configs.items():
        if set(config)-allowed:raise ValueError('unknown config fields '+kind+repr(set(config)-allowed))
        for k,v in config.items():
            if not (isinstance(v,str) if k=='head' else type(v) is bool if k in FLAGS else type(v) in (int,float)):raise ValueError('untyped config '+kind+'/'+k)
    header='''// Effective PvP plant-zombie definitions; generated from the installed source.
#pragma once
#include "sim/typed/projectile_rules.h"
#include <span>
namespace pvz::typed72 {
'''
    for macro,fields in (('PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS',NUMBERS),('PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS',FLAGS)):
        header+='#define '+macro+'(X) '+ ' '.join('X('+key+')' for key in fields)+'\n'
    header+='''struct PlantZombieConfig {
    std::string_view kind;
    std::string head;
#define NUM(n) Field<double> n;
    PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(NUM)
#undef NUM
#define FLAG(n) Field<bool> n;
    PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(FLAG)
#undef FLAG
};
std::span<const PlantZombieConfig> native_plant_zombie_catalog();
const PlantZombieConfig* native_plant_zombie_config(std::string_view);
void load_native_plant_zombie_heads(CollisionCatalog&);
} // namespace pvz::typed72
'''
    body='''// Generated constants after NativeCombatPatch's current PvP overrides.
#include "sim/typed/plant_zombie_catalog.h"
#include <array>
namespace pvz::typed72 {
std::span<const PlantZombieConfig> native_plant_zombie_catalog() {
    static const auto entries=[] {
'''
    body+='        std::array<PlantZombieConfig,'+str(len(configs))+'> values;\n'
    for i,(kind,config) in enumerate(configs.items()):
        body+='        {auto& c=values['+str(i)+'];c.kind='+json.dumps(kind,ensure_ascii=False)+';c.head='+json.dumps(config['head'],ensure_ascii=False)+';\n'
        for key,value in config.items():
            if key=='head':continue
            literal=('true' if value else 'false') if type(value) is bool else float(value).hex()
            body+='            c.'+key+'.set('+literal+');\n'
        body+='        }\n'
    body+='''        return values;
    }();return entries;
}
const PlantZombieConfig* native_plant_zombie_config(std::string_view kind) {
    for(const auto& c:native_plant_zombie_catalog())if(c.kind==kind)return &c;return nullptr;
}
void load_native_plant_zombie_heads(CollisionCatalog& catalog) {
    for(const auto& c:native_plant_zombie_catalog())
        catalog.plant_heads[std::string(c.kind)]={c.head_x.or_missing(.08),c.head_y.or_missing(1.35),
            c.duck_head_x.or_missing(.08),c.duck_head_y.or_missing(1.35),c.head_scale.or_missing(.68),
            c.fire_anim.or_missing(catalog.default_fire_frames),c.fumeshroom.or_missing(false)};
}
} // namespace pvz::typed72
'''
    generated={}
    for name,text in (('plant_zombie_catalog.h',header),('plant_zombie_catalog.cpp',body)):
        path=out/name
        if path.exists():raise FileExistsError(path)
        path.write_text(text,encoding='utf8');generated[str(path)]=sha(path)
    inputs=proxy_reference.paths()+[raw,Path(__file__).resolve()]
    report=dict(source={str(p):sha(p) for p in inputs},generated=generated,configurations=configs,kind_count=len(configs),
        full_product_acceptance=False,validation_pending=True)
    (evidence/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(kinds=len(configs),fields=len(allowed),validation_pending=True)))


if __name__=='__main__':main()
