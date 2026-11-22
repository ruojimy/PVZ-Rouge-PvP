"""Relink the headless training front ends against the shipped PvP75 r3 rules and data (2026-11-21, after r4 was retired)."""
import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from league_data import R, ROOT, H, BUILD, sha, read, write

OUT=ROOT/'ranked-pvp75-20261121'
NATIVE=OUT/'native'
WORK=R/'build/pvp75train21'
RELEASE=read(R/'dist/latest-native-release.json')
SHIPPED=Path(RELEASE['target']).parent
LIB=R/'build/app-typed72-v2/Release'

def build():
    assert RELEASE['revision']=='pvp75-r3' and sha(Path(RELEASE['target']))==RELEASE['exe_sha256']
    assert sha(Path(RELEASE['developer_package']))==RELEASE['developer_sha256']
    root=WORK/'src';root.mkdir(parents=True,exist_ok=True);NATIVE.mkdir(parents=True,exist_ok=True)
    app='src/sim/typed72_app';kernel='build/typed72-integrated-v44/source/src/sim/typed'
    paths=set()
    for folder,exts in [(kernel,('cpp','h')),(app+'/composition',('cpp','h','inc')),(app+'/ai',('cpp','h'))]:
        for ext in exts:paths.update(p.relative_to(R).as_posix() for p in (R/folder).rglob('*.'+ext))
    paths.update(p.relative_to(R).as_posix() for p in (R/app).glob('*.h'))
    paths.update(app+'/'+n for n in ('session.cpp','ai_planner_r22.cpp'))
    with zipfile.ZipFile(RELEASE['developer_package']) as z:
        prefix=z.namelist()[0].split('/')[0]+'/'
        hashes={}
        for name in sorted(paths):
            h=hashlib.sha256(z.read(prefix+name)).hexdigest()
            assert h==sha(R/name),name
            hashes[name]=h
        assert sha(R/app/'cold_file.cpp')==hashlib.sha256(z.read(prefix+app+'/cold_file.cpp')).hexdigest() if prefix+app+'/cold_file.cpp' in z.namelist() else True
        # Link official translation units directly when the working tree has moved beyond the release.
        overrides=[]
        for n in z.namelist():
            name=n[len(prefix):];p=R/name
            if not name.startswith(('src/sim/','src/ui/','src/core/','src/pg/','src/data/')) or p.suffix not in ('.h','.inc','.cpp'):continue
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
        throw std::runtime_error("expected released PvP75 ranked seven-slot duel");
    auto session=Session::create(std::move(cold),entry.map);''')
    txt=txt.replace('header["seq_base"]=o.seq_base;', 'header["ranked_rules"]=rules;header["source_fingerprint"]=AI_NN_SIM_FINGERPRINT;header["seq_base"]=o.seq_base;')
    main.write_text(txt,'utf8')
    libs=[LIB/(n+'.lib') for n in ('pvzui','pvztyped72app','pvztyped72kernel','pvzcore','pvzsnapshot_zlib')]
    sdl=R/'third_party/SDL2-2.30.9/lib/x64/SDL2.lib'
    other=[R/f'third_party/SDL2_{n}-{v}/lib/x64/SDL2_{n}.lib' for n,v in [('image','2.8.2'),('ttf','2.22.0'),('mixer','2.8.0')]]
    def cm(args):return ' '.join('"'+Path(v).as_posix()+'"' for v in args)
    c=['cmake_minimum_required(VERSION 3.20)','project(RankedPvP75 CXX)','set(CMAKE_CXX_STANDARD 20)',
       'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)','add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN SDL_MAIN_HANDLED _CRT_SECURE_NO_WARNINGS)',
       'add_compile_options(/O2 /fp:precise /utf-8 /bigobj /EHsc /GR /w)',
       'include_directories('+cm([root,R/kernel.split('/sim/typed')[0],R/app/'composition',R/app/'composition/probes',R/'src',R/'third_party',R/'tools/typed72',R/'third_party/SDL2-2.30.9/include',H/'src'])+')']
    # Prioritize the source include directory of the frozen integrated kernel.
    c.append('include_directories(BEFORE "'+(R/'build/typed72-integrated-v44/source/src').as_posix()+'")')
    for name,extra in [('ranked_draft_room',[]),('cold73_export',[R/'src/sim/pvp/battle_api.cpp'])]:
        c+=['add_executable('+name+' '+cm([R/f'build/pvp73-tools/{name}.cpp',*[root/n for n in overrides],*extra])+')',
            'target_link_libraries('+name+' PRIVATE '+cm([*libs,sdl,*other])+' ws2_32)']
    c+=['add_executable(position_match '+cm([root/'position_match.cpp',root/'tactical_session.cpp',H/'research_utf8.manifest',
          *[R/app/n for n in ('cold_file.cpp','ai_planner_r22.cpp','ai/controller.cpp','ai/layers7.cpp','ai/layers11.cpp','ai/layers19.cpp')]])+')',
        'target_compile_definitions(position_match PRIVATE PVZ_AI_NN_PLAIN_FILES)',
        'target_link_libraries(position_match PRIVATE '+cm([LIB/'pvztyped72kernel.lib',sdl])+')']
    (root/'CMakeLists.txt').write_text('\n'.join(c)+'\n','utf8')
    cmake=re.search(r'^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M)[1]
    subprocess.run([cmake,'-S',root,'-B',WORK/'obj','-G','Visual Studio 17 2022','-A','x64'],check=True)
    subprocess.run([cmake,'--build',WORK/'obj','--config','Release','--parallel','4'],check=True)
    names=('ranked_draft_room','cold73_export','position_match')
    for name in names:
        src=WORK/'obj/Release'/(name+'.exe');dst=NATIVE/src.name
        if not dst.exists():dst.hardlink_to(src)
        assert sha(src)==sha(dst)
    for dll in (SHIPPED).glob('SDL2*.dll'):
        target=NATIVE/dll.name
        if not target.exists():target.hardlink_to(dll)
    write(OUT/'native-build.json',dict(version=RELEASE['version'],release=RELEASE['exe_sha256'],developer_package=RELEASE['developer_sha256'],
          source_files=len(hashes),fingerprint=fp,release_overrides=overrides,data_root=str(SHIPPED),libraries={p.name:sha(p) for p in libs},
          binaries={n:sha(NATIVE/(n+'.exe')) for n in names},shipped_catalog=sha(SHIPPED/'extract/data/_resolved_cards.json')))

if __name__=='__main__':build()
