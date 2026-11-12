"""Integrate prepared squash sources only after the fumeshroom proof closes."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
    checkpoint=ROOT/'test_results/typed72-20261105/checkpoint-fume-chain/status.json'
    state=json.loads(checkpoint.read_text(encoding='utf8'))
    assert state['schema']==15 and len(state['verification'])==38
    for name,digest in state['source_files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    draft=Path(__file__).resolve().parent
    for name in ('squash_state.h','ballistics.h','ballistics.cpp','squash_effects.h','squash_effects.cpp'):
        destination=ROOT/'src/sim/typed'/name;assert not destination.exists();shutil.copy2(draft/name,destination)
    for name in ('squash_probe.cpp','verify_squash.py','negative_squash.py'):
        destination=ROOT/'tools/typed72'/name;assert not destination.exists();shutil.copy2(draft/name,destination)
    p=ROOT/'src/sim/typed/combat_events.h';s=p.read_text(encoding='utf8');s=s.replace('// One typed journal','struct SquashSplashEvent {std::optional<std::string> entity;};\n// One typed journal');s=s.replace('BasketballHitEvent,MelonSplashEvent>','BasketballHitEvent,MelonSplashEvent,SquashSplashEvent>');p.write_text(s,encoding='utf8')
    p=ROOT/'tools/typed72/hero_probe.cpp';s=p.read_text(encoding='utf8');s=s.replace('    const auto& e=std::get<MelonSplashEvent>(event);','    if(const auto* e=std::get_if<SquashSplashEvent>(&event))return {{"type","squash_splash"},{"entity",e->entity?J(*e->entity):J(nullptr)}};\n    const auto& e=std::get<MelonSplashEvent>(event);');p.write_text(s,encoding='utf8')
    p=ROOT/'src/sim/typed/state.h';s=p.read_text(encoding='utf8');s=s.replace('#include "sim/typed/service_state.h"','#include "sim/typed/service_state.h"\n#include "sim/typed/squash_state.h"');s=s.replace('    EntityServiceState service;','    EntityServiceState service;\n    SquashState squash;');p.write_text(s,encoding='utf8')
    p=ROOT/'src/sim/typed/targets.h';s=p.read_text(encoding='utf8');s=s.replace('    Field<bool> umbrella_secret,umbrella_initialized;','    Field<bool> umbrella_secret,umbrella_initialized;\n    Field<bool> squash_used;');s=s.replace('    FumeState fume;','    FumeState fume;\n    BallisticHistory ballistics;');p.write_text(s,encoding='utf8')
    p=ROOT/'src/sim/typed/CMakeLists.txt';s=p.read_text(encoding='utf8');s+='\nset(PVZ_TYPED_BALLISTICS_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/ballistics.cpp" CACHE FILEPATH "Native ballistics negative control")\nset(PVZ_TYPED_SQUASH_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/squash_effects.cpp" CACHE FILEPATH "Native squash negative control")\ntarget_sources(pvztyped72 PRIVATE "${PVZ_TYPED_BALLISTICS_SOURCE}" "${PVZ_TYPED_SQUASH_SOURCE}")\nadd_executable(squash72_probe "${PVZ_TYPED_ROOT}/tools/typed72/squash_probe.cpp")\ntarget_link_libraries(squash72_probe PRIVATE pvztyped72)\ntarget_include_directories(squash72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party")\n';p.write_text(s,encoding='utf8')
    print('Prepared squash sources integrated; compilation and differential verification still required.')
if __name__=='__main__':main()
