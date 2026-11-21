"""Isolate the experiment's tactical decision layer and link to the frozen simulation library."""
import re
import shutil
from position_study import OUT, R, H, BUILD, BIN, inputs_ok, cmd, sha, write


def replace_once(text, old, new):
    assert text.count(old)==1,old
    return text.replace(old,new)


def build():
    inputs_ok()
    source=OUT/'native-src'
    source.mkdir(exist_ok=True)
    shutil.copy2(H/'position_head.h',source/'position_head.h')
    session=(R/'src/sim/typed72_app/session.cpp').read_text('utf8')
    session=replace_once(session,'namespace pvz::typed72app {','#include "position_head.h"\nnamespace pvz::typed72app {')
    session=replace_once(session,'class TypedSession final:public Session {','class TypedSession final:public Session {\n    position_ai::Tactics tactics_;')
    session=replace_once(session,'slot->send=std::move(send);','''position_ai::Hints suggestions;
        const bool tactical=position_ai::active && side==Seat::zombie;
        if(tactical)slot->send=[&](const std::string& k,const ai::Args& a){return suggestions.capture(k,a,send);};
        else slot->send=std::move(send);''')
    session=replace_once(session,'ctl->step(view,*last_observation_[i],*last_plan_[i],*field_,services);',
        '''ctl->step(view,*last_observation_[i],*last_plan_[i],*field_,services);
        if(tactical){slot->send={};tactics_.step(view,*field_,services,suggestions,send);}''')
    (source/'tactical_session.cpp').write_text(session,'utf8')
    main=(H/'src/headless_match.cpp').read_text('utf8')
    main=replace_once(main,'#include "plan_codec.h"','#include "position_head.h"\n#include "plan_codec.h"')
    main=replace_once(main,'std::string dump_inputs,inputs,log,final_snapshot;','std::string dump_inputs,inputs,log,final_snapshot,position_model;')
    main=replace_once(main,'auto session=Session::create','position_ai::load(o.position_model);\n    auto session=Session::create')
    main=replace_once(main,'J activity=J::array();','J activity=J::array(), commands=J::array();')
    main=replace_once(main,'const std::string line=event.dump', '''if(o.telemetry && event.value("event",std::string{})=="input" && event.value("side",std::string{})=="zombie"){
                const auto kind=event.value("kind",std::string{});
                if(kind=="rally"||kind=="deploy")commands.push_back(event);
            }
            const std::string line=event.dump''')
    main=replace_once(main,'if(o.telemetry)footer["activity"]=std::move(activity);',
        'if(o.telemetry){footer["activity"]=std::move(activity);footer["spatial_actions"]=std::move(position_ai::events);footer["accepted_commands"]=std::move(commands);}')
    main=replace_once(main,'else if(a=="--nn-seat")','else if(a=="--position-model")o.position_model=value();\n        else if(a=="--nn-seat")')
    main=replace_once(main,'std::vector<SeatAi> seats;', '''if(!o.position_model.empty()){
        ainn::Sha256 hash;hash.update(read_file_maybe_gz(o.position_model));header["zombie_position_sha256"]=hash.hex();
    }
    std::vector<SeatAi> seats;''')
    (source/'position_match.cpp').write_text(main,'utf8')
    cmake=replace_once('''cmake_minimum_required(VERSION 3.20)
project(SpatialReadout CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
set(ROOT "@ROOT@")
set(FROZEN "${ROOT}/build/ai-nn/windows-policy2-20261118")
add_executable(position_match position_match.cpp tactical_session.cpp "${ROOT}/build/ai-nn/research_utf8.manifest")
target_include_directories(position_match PRIVATE "${ROOT}/build/typed72-integrated-v44/source/src" "${ROOT}/src/sim/typed72_app/composition" "${ROOT}/src/sim/typed72_app/composition/probes" "${FROZEN}" "${ROOT}/src" "${ROOT}/third_party" "${ROOT}/tools/typed72" "${ROOT}/third_party/SDL2-2.30.9/include" "${ROOT}/build/ai-nn/src")
target_compile_definitions(position_match PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN SDL_MAIN_HANDLED PVZ_AI_NN_PLAIN_FILES)
target_compile_options(position_match PRIVATE /O2 /fp:precise /utf-8 /bigobj /EHsc /GR /w)
target_link_libraries(position_match PRIVATE "${FROZEN}/Release/pvztyped72headless.lib" "${FROZEN}/Release/pvztyped72kernel.lib" "${ROOT}/third_party/SDL2-2.30.9/lib/x64/SDL2.lib")
''','@ROOT@',R.as_posix())
    (source/'CMakeLists.txt').write_text(cmake,'utf8')
    exe=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(exe,'-S',source,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(exe,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copy2(BIN/'SDL2.dll',OUT/'native/Release/SDL2.dll')
    write(OUT/'build.json',dict(sources={k:sha(source/k) for k in ['CMakeLists.txt','position_head.h','tactical_session.cpp','position_match.cpp']},
          libraries={p.name:sha(p) for p in BIN.glob('*.lib')},binary=sha(OUT/'native/Release/position_match.exe')))

