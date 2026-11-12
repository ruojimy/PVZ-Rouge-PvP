"""Integrate pea sources after the unchanged squash chain closes."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def edit(name,old,new,count=1):
    p=ROOT/name;s=p.read_text(encoding='utf8');assert s.count(old)==count,(name,old,s.count(old));p.write_text(s.replace(old,new),encoding='utf8')

def main():
    state=json.loads((ROOT/'test_results/typed72-20261105/checkpoint-squash-chain/status.json').read_text(encoding='utf8'))
    assert state['schema']==16 and len(state['verification'])==40
    for name,digest in state['source_files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for name in ('zombie_pea_state.h','zombie_pea.h','zombie_pea.cpp','pea_probe.cpp','verify_peas.py'):
        dest=ROOT/('src/sim/typed' if name.startswith('zombie_') else 'tools/typed72')/name;assert not dest.exists();shutil.copy2(Path(__file__).parent/name,dest)
    edit('src/sim/typed/state.h','#include "sim/typed/squash_state.h"','#include "sim/typed/squash_state.h"\n#include "sim/typed/zombie_pea_state.h"')
    edit('src/sim/typed/state.h','    SquashState squash;','    SquashState squash;\n    ZombiePeaState pea;\n    Field<RecordId> native_source_zombie;\n    Field<double> tracking;')
    edit('src/sim/typed/squash_state.h','    Field<RecordId> source_zombie;\n','')
    edit('src/sim/typed/squash_effects.cpp','q.source_zombie.set(u->identity);','e->native_source_zombie.set(u->identity);')
    p=ROOT/'tools/typed72/squash_probe.cpp';s=p.read_text(encoding='utf8');assert s.count('q.source_zombie')==2
    s=s.replace('id_read(v,"__pvz_sb_source_zombie_id",q.source_zombie);','id_read(v,"__pvz_sb_source_zombie_id",e.native_source_zombie);')
    s=s.replace('id_write(j,"__pvz_sb_source_zombie_id",q.source_zombie);','id_write(j,"__pvz_sb_source_zombie_id",e->native_source_zombie);')
    assert s.count('int main(')==1;s=s.replace('int main(','#ifndef PVZ72_SQUASH_PROBE_EMBEDDED\nint main(');s+='\n#endif\n';p.write_text(s,encoding='utf8')
    edit('src/sim/typed/targets.h','    Field<bool> squash_used;','    Field<bool> squash_used;\n    Field<double> shotgun_volley;')
    edit('src/sim/typed/targets.h','    BallisticHistory ballistics;','    BallisticHistory ballistics;\n    ZombiePeaWorld zombie_peas;')
    edit('src/sim/typed/hero.h','    std::optional<AttackIdentity> launch_attack;','    Field<double> pea_angle;\n    std::optional<AttackIdentity> launch_attack;')
    edit('src/sim/typed/combat_events.h','// One typed journal','struct ZombieHeroPeaEvent {Seat seat;};\n// One typed journal')
    edit('src/sim/typed/combat_events.h','MelonSplashEvent,SquashSplashEvent>','MelonSplashEvent,SquashSplashEvent,ZombieHeroPeaEvent>')
    edit('tools/typed72/hero_probe.cpp','"_pvp_regen_progress","_pvp_seat"','"_pvp_regen_progress","_pvp_seat","_pvp_pea_angle"')
    edit('tools/typed72/hero_probe.cpp','read(j,"_pvp_regen_progress",h.regen_progress);','read(j,"_pvp_regen_progress",h.regen_progress);read(j,"_pvp_pea_angle",h.pea_angle);')
    edit('tools/typed72/hero_probe.cpp','write(j,"_pvp_regen_progress",h.regen_progress);','write(j,"_pvp_regen_progress",h.regen_progress);write(j,"_pvp_pea_angle",h.pea_angle);')
    edit('tools/typed72/hero_probe.cpp','    const auto& e=std::get<MelonSplashEvent>(event);','    if(const auto* e=std::get_if<ZombieHeroPeaEvent>(&event))return {{"type","zsecret_hero_pea"},{"side",seat_name(e->seat)}};\n    const auto& e=std::get<MelonSplashEvent>(event);')
    edit('tools/typed72/hero_probe.cpp','std::holds_alternative<SquashSplashEvent>(e))','std::holds_alternative<SquashSplashEvent>(e)||std::holds_alternative<ZombieHeroPeaEvent>(e))')
    p=ROOT/'src/sim/typed/CMakeLists.txt';s=p.read_text(encoding='utf8');s+='\nset(PVZ_TYPED_PEA_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/zombie_pea.cpp" CACHE FILEPATH "Native zombie pea negative control")\ntarget_sources(pvztyped72 PRIVATE "${PVZ_TYPED_PEA_SOURCE}")\nadd_executable(pea72_probe "${PVZ_TYPED_ROOT}/tools/typed72/pea_probe.cpp")\ntarget_link_libraries(pea72_probe PRIVATE pvztyped72)\ntarget_include_directories(pea72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party")\n';p.write_text(s,encoding='utf8')
    edit('tools/typed72/verify_components.py',"('squash','verify_squash.py','squash72_probe.exe')]","('squash','verify_squash.py','squash72_probe.exe'),('peas','verify_peas.py','pea72_probe.exe')]")
    edit('tools/typed72/build_android_components.py',"'fume','squash']","'fume','squash','pea']")
    print('Pea sources integrated; build and differential verification remain required.')

if __name__=='__main__':main()
