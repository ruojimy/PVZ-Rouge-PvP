"""Link the ranked training front ends against the verified installed release."""
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from league_data import R, ROOT, H, BUILD, sha, read, write

OUT=ROOT/'ranked-pvp75-20261121'
NATIVE=OUT/'native'
WORK=R/'build/pvp75train21'
RELEASE=read(R/'dist/latest-native-release.json')
SHIPPED=Path(RELEASE['target']).parent
LIB=R/'build/app-typed72-v2/Release'

def wire_deploy_research(txt):
    switches = [
        ('#include "plan_codec.h"', '#include "plan_codec.h"\n#include "deploy_model.h"'),
        ('bool records=true,telemetry=false;', '''bool records=true,telemetry=false;
    std::string deploy_trace,deploy_model,deploy_side;
    double deploy_margin=0.35;'''),
        ('auto session=Session::create(std::move(cold),entry.map);',
         '''auto session=Session::create(std::move(cold),entry.map);
    deploy_research::DeployPolicy deployment(o.deploy_trace,o.deploy_model,o.deploy_side,o.deploy_margin);'''),
        ('header["seq_base"]=o.seq_base;', 'header["seq_base"]=o.seq_base;header["deploy_controller"]=deployment.metadata();'),
        ('''J payload=args_json(kind,++s.seq,data);
                    const auto error=session->command(s.name,payload);   // AISeat.send -> Room.command -> command_input
                    ++s.sends;if(!error.empty())++s.send_errors;
                    if(!o.dump_inputs.empty()){payload.erase("seq");payload["side"]=s.name;dumped[tick_key].push_back(std::move(payload));}
                    return error;''',
         '''const J payload=args_json(kind,++s.seq,data);
                    return deployment.dispatch(*session,s.seat,s.name,payload,[&](J attempt,bool retry){
                        if(retry)attempt["seq"]=++s.seq;
                        const auto error=session->command(s.name,attempt);
                        ++s.sends;if(!error.empty())++s.send_errors;
                        if(!o.dump_inputs.empty()){attempt.erase("seq");attempt["side"]=s.name;dumped[tick_key].push_back(std::move(attempt));}
                        return error;
                    });'''),
        ('footer["ai"]=ai;', 'footer["ai"]=ai;footer["deploy_policy"]=deployment.counts();'),
        ('else if(a=="--telemetry")o.telemetry=true;', '''else if(a=="--telemetry")o.telemetry=true;
        else if(a=="--deploy-trace")o.deploy_trace=value();
        else if(a=="--deploy-model")o.deploy_model=value();
        else if(a=="--deploy-side")o.deploy_side=value();
        else if(a=="--deploy-margin")o.deploy_margin=std::stod(value());'''),
        ('    return o;', '''    if((!o.deploy_model.empty() && o.deploy_side!="plant" && o.deploy_side!="zombie")
       || !std::isfinite(o.deploy_margin) || o.deploy_margin<0.)
        throw std::invalid_argument("Deploy model needs one seat and a finite nonnegative margin");
    if((!o.deploy_model.empty()||!o.deploy_trace.empty())&&o.ids.size()!=1)
        throw std::invalid_argument("Deploy research accepts one opening per invocation");
    return o;'''),
    ]
    for before, after in switches:
        assert txt.count(before) == 1, before
        txt = txt.replace(before, after)
    return txt


def wire_card_support(txt):
    switches = [
        ('#include "deploy_model.h"', '#include "deploy_model.h"\n#include "laser_basics.h"'),
        ('double deploy_margin=0.35;', 'double deploy_margin=0.35;\n    bool laser_basics=false;'),
        ('deploy_research::DeployPolicy deployment', 'laser_research::Controller laser;\n    deploy_research::DeployPolicy deployment'),
        ('(void)session->ai_control(s.seat,"r22",', '''if(o.laser_basics && s.seat==Seat::plant
                   && std::find(s.deck.begin(),s.deck.end(),laser_research::Card)!=s.deck.end()){
                    laser.step(*session,time,[&](const std::string& type,J data){
                        data["type"]=type;
                        data["seq"]=++s.seq;
                        const auto error=session->command(s.name,data);
                        ++s.sends;if(!error.empty())++s.send_errors;
                        if(!o.dump_inputs.empty()){data.erase("seq");data["side"]=s.name;dumped[tick_key].push_back(std::move(data));}
                        return error;
                    });
                }
                (void)session->ai_control(s.seat,"r22",'''),
        ('footer["deploy_policy"]=deployment.counts();', '''footer["deploy_policy"]=deployment.counts();
    footer["laser_basics"]=laser.counts();
    const auto laser_stats=session->performance_counters();
    footer["laser_basics"]["beam_pulses"]=laser_stats.at("laser_beam_pulses");
    footer["laser_basics"]["focus_hits"]=laser_stats.at("laser_focus_hits");'''),
        ('else if(a=="--deploy-trace")', 'else if(a=="--laser-basics")o.laser_basics=true;\n        else if(a=="--deploy-trace")'),
        ('const Options o=parse(argc,argv);', '''if(argc==2 && std::string(argv[1])=="--model-contract"){
            const pvz::typed72::ColdCatalog catalog;
            std::cout<<J{{"catalog_hash",catalog.data().catalog_hash},{"rules_hash",catalog.data().rules_hash},
                        {"behaviors",ainn::neural_behaviors()},{"sim_fingerprint",AI_NN_SIM_FINGERPRINT}}.dump()<<'\\n';
            return 0;
        }
        const Options o=parse(argc,argv);'''),
    ]
    for before, after in switches:
        assert txt.count(before) == 1, before
        txt = txt.replace(before, after)
    return txt


def build(revision='pvp75-r3', output=OUT, work=WORK, *, card_support=False, r22_cards=False):
    native=output/'native'
    assert RELEASE['revision']==revision and sha(Path(RELEASE['target']))==RELEASE['exe_sha256']
    assert sha(Path(RELEASE['developer_package']))==RELEASE['developer_sha256']
    if revision in ('pvp76-r3','pvp77-r2','pvp77-r4','pvp78-r3'):
        assert sha(LIB/'PvZPvPNative.exe')==RELEASE['exe_sha256']
        assert sha(Path(RELEASE['release'])/'PvZPvPNative.exe')==RELEASE['exe_sha256']
    root=work/'src';root.mkdir(parents=True,exist_ok=True);native.mkdir(parents=True,exist_ok=True)
    app='src/sim/typed72_app';kernel='build/typed72-integrated-v44/source/src/sim/typed'
    paths=set()
    for folder,exts in [(kernel,('cpp','h')),(app+'/composition',('cpp','h','inc')),(app+'/ai',('cpp','h'))]:
        for ext in exts:paths.update(p.relative_to(R).as_posix() for p in (R/folder).rglob('*.'+ext))
    paths.update(p.relative_to(R).as_posix() for p in (R/app).glob('*.h'))
    paths.update(app+'/'+n for n in ('session.cpp','ai_planner_r22.cpp'))
    ai_patch=set()
    if r22_cards:
        ai_patch={f'{app}/{name}' for name in
                  ('session.cpp','ai/view.h','ai/layers19.h','ai/layers19.cpp','ai/r22_new_cards.inc')}
        ai_patch.update(('src/ui/gen/pm_lobby_room.cpp','src/ui/hand/ranked_fast_heads.h'))
    paths.update(ai_patch)
    patched={}
    with zipfile.ZipFile(RELEASE['developer_package']) as z:
        prefix=z.namelist()[0].split('/')[0]+'/'
        hashes={}
        for name in sorted(paths):
            h=sha(R/name)
            if name in ai_patch:
                baseline=hashlib.sha256(z.read(prefix+name)).hexdigest() if prefix+name in z.namelist() else None
                patched[name]={'release':baseline,'candidate':h}
            else:
                assert h==hashlib.sha256(z.read(prefix+name)).hexdigest(),name
            hashes[name]=h
        assert sha(R/app/'cold_file.cpp')==hashlib.sha256(z.read(prefix+app+'/cold_file.cpp')).hexdigest() if prefix+app+'/cold_file.cpp' in z.namelist() else True
        # Link official translation units directly when the working tree has moved beyond the release.
        overrides=[]
        for n in z.namelist():
            name=n[len(prefix):];p=R/name
            if not name.startswith(('src/sim/','src/ui/','src/core/','src/pg/','src/data/')) or p.suffix not in ('.h','.inc','.cpp'):continue
            if name in ai_patch:continue
            if p.read_bytes()==z.read(n):continue
            assert p.suffix=='.cpp',name
            (root/p.name).write_bytes(z.read(n));overrides.append(p.name)
        for n in z.namelist():
            name=n[len(prefix):]
            if name.startswith('extract/data/') and name.endswith('.json'):
                assert (SHIPPED/name).read_bytes()==z.read(n),name
    fp=hashlib.sha256(''.join(f'{n}:{h}\n' for n,h in sorted(hashes.items())).encode()).hexdigest()
    (root/'ai_nn_build.h').write_text('#pragma once\n#define AI_NN_SIM_FINGERPRINT "'+fp+'"\n','utf8')
    previous_src=ROOT/'zombie-special-2h-20261119/native-src'
    verified=read(ROOT/'zombie-special-2h-20261119/build.json')['sources']
    for name,h in verified.items():
        if name=='CMakeLists.txt':continue
        assert sha(previous_src/name)==h
        shutil.copyfile(previous_src/name,root/name)
    # The current code validates the actual cold battle at the simulator entry point as well.
    main=root/'position_match.cpp';txt=main.read_text('utf8')
    before='auto session=Session::create(load_corpus_entry(entry),entry.map);'
    assert txt.count(before)==1
    txt=txt.replace(before,'''auto cold=load_corpus_entry(entry);
    const auto rules=cold.cold.at("battle").at("rules");
    if(!rules.at("ranked").get<bool>() || rules.at("extra_slot").get<bool>() ||
       rules.at("plant_slots")!=7 || rules.at("zombie_slots")!=7 ||
       rules.at("build")!="'''+RELEASE['version']+'''" || entry.plant_deck.size()!=7 || entry.zombie_deck.size()!=7)
        throw std::runtime_error("expected released ranked seven-slot duel");
    auto session=Session::create(std::move(cold),entry.map);''')
    txt=txt.replace('header["seq_base"]=o.seq_base;', 'header["ranked_rules"]=rules;header["source_fingerprint"]=AI_NN_SIM_FINGERPRINT;header["seq_base"]=o.seq_base;')
    if revision=='pvp77-r4':
        txt=wire_deploy_research(txt)
    if card_support:
        txt=wire_card_support(txt)
        session_file=root/'tactical_session.cpp'
        session_txt=session_file.read_text('utf8')
        marker='{"primal_knock_targets",match_->content_damage.primal_knock_targets}'
        assert session_txt.count(marker)==1
        session_file.write_text(session_txt.replace(marker,
            '{"laser_beam_pulses",match_->pvp75.beam_pulses},{"laser_focus_hits",match_->pvp75.focus_hits},'+marker), 'utf8')
    if r22_cards:
        marker='footer["ai"]=ai;'
        assert txt.count(marker)==1
        txt=txt.replace(marker, marker+'''
    const auto counters=session->performance_counters();
    for(const auto* key:{"laser_beam_pulses","laser_focus_hits","croton_triggers","croton_gas_hits"})
        footer["card_mechanics"][key]=counters.at(key);''')
    main.write_text(txt,'utf8')
    libs=[LIB/(n+'.lib') for n in ('pvzui','pvztyped72app','pvztyped72kernel','pvzcore','pvzsnapshot_zlib')]
    sdl=R/'third_party/SDL2-2.30.9/lib/x64/SDL2.lib'
    other=[R/f'third_party/SDL2_{n}-{v}/lib/x64/SDL2_{n}.lib' for n,v in [('image','2.8.2'),('ttf','2.22.0'),('mixer','2.8.0')]]
    def cm(args):return ' '.join('"'+Path(v).as_posix()+'"' for v in args)
    c=['cmake_minimum_required(VERSION 3.20)','project(RankedTraining CXX)','set(CMAKE_CXX_STANDARD 20)',
       'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)','add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN SDL_MAIN_HANDLED _CRT_SECURE_NO_WARNINGS)',
       'add_compile_options(/O2 /fp:precise /utf-8 /bigobj /EHsc /GR /w)',
       'include_directories('+cm([root,R/kernel.split('/sim/typed')[0],R/app/'composition',R/app/'composition/probes',R/'src',R/'third_party',R/'tools/typed72',R/'third_party/SDL2-2.30.9/include',H/'src'])+')']
    # Prioritize the source include directory of the frozen integrated kernel.
    c.append('include_directories(BEFORE "'+(R/'build/typed72-integrated-v44/source/src').as_posix()+'")')
    lobby=[R/'src/ui/gen/pm_lobby_room.cpp'] if r22_cards else []
    for name,extra in [('ranked_draft_room',lobby),('cold73_export',[R/'src/sim/pvp/battle_api.cpp',*lobby])]:
        c+=['add_executable('+name+' '+cm([R/f'build/pvp73-tools/{name}.cpp',*[root/n for n in overrides],*extra])+')',
            'target_link_libraries('+name+' PRIVATE '+cm([*libs,sdl,*other])+' ws2_32)']
    session=R/app/'session.cpp' if r22_cards else root/'tactical_session.cpp'
    c+=['add_executable(position_match '+cm([root/'position_match.cpp',session,H/'research_utf8.manifest',
          *[R/app/n for n in ('cold_file.cpp','ai_planner_r22.cpp','ai/controller.cpp','ai/layers7.cpp','ai/layers11.cpp','ai/layers19.cpp')]])+')',
        'target_compile_definitions(position_match PRIVATE PVZ_AI_NN_PLAIN_FILES)',
        'target_link_libraries(position_match PRIVATE '+cm([LIB/'pvztyped72kernel.lib',sdl])+')']
    (root/'CMakeLists.txt').write_text('\n'.join(c)+'\n','utf8')
    cmake=re.search(r'^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M)[1]
    subprocess.run([cmake,'-S',root,'-B',work/'obj','-G','Visual Studio 17 2022','-A','x64'],check=True)
    subprocess.run([cmake,'--build',work/'obj','--config','Release','--parallel','4'],check=True)
    names=('ranked_draft_room','cold73_export','position_match')
    for name in names:
        src=work/'obj/Release'/(name+'.exe');dst=native/src.name
        if src!=dst:shutil.copy2(src,dst)
        assert sha(src)==sha(dst)
    for dll in (SHIPPED).glob('SDL2*.dll'):
        target=native/dll.name
        if not target.exists():target.hardlink_to(dll)
    write(output/'native-build.json',dict(version=RELEASE['version'],release=RELEASE['exe_sha256'],developer_package=RELEASE['developer_sha256'],
          source_files=len(hashes),fingerprint=fp,release_overrides=overrides,data_root=str(SHIPPED),libraries={p.name:sha(p) for p in libs},
          draft_probe=sha(R/'build/pvp73-tools/ranked_draft_room.cpp'), candidate_sources=patched,
          binaries={n:sha(native/(n+'.exe')) for n in names},shipped_catalog=sha(SHIPPED/'extract/data/_resolved_cards.json')))

if __name__=='__main__':
    if sys.argv[1:]==['pvp76-r3']:
        build('pvp76-r3',ROOT/'deck-value-pvp76-r3-20261123',R/'build/pvp76r3-train')
    elif sys.argv[1:]==['pvp77-r2']:
        build('pvp77-r2',ROOT/'deck-value-pvp77-r2-20261123',R/'build/pvp77r2-train')
    elif sys.argv[1:]==['pvp77-r4']:
        build('pvp77-r4',ROOT/'battle-control-pvp77-r4-20261124',R/'build/pvp77r4-action-train')
    elif sys.argv[1:]==['pvp77-r4-card-support']:
        build('pvp77-r4',ROOT/'card-support-pvp77-r4-20261124',R/'build/pvp77r4-card-support',card_support=True)
    elif sys.argv[1:]==['pvp78-r3-r22-cards']:
        build('pvp78-r3',ROOT/'r22-cards-native-draft-pvp78-r3-20261125',R/'build/pvp78r3-r22-cards',r22_cards=True)
    elif not sys.argv[1:]:
        build()
    else:
        sys.exit('Usage: ranked_pvp75_native.py [pvp76-r3|pvp77-r2|pvp77-r4|pvp77-r4-card-support|pvp78-r3-r22-cards]')
