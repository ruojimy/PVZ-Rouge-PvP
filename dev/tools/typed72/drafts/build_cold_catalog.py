"""Serial build for typed catalog and the matching retained-V query oracle."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
import evidence_store
ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,default=ROOT/'build/typed72-cold-catalog-v2');a=ap.parse_args()
stage=a.stage.resolve()
stage.mkdir(exist_ok=False);frozen=stage/'frozen';frozen.mkdir()
drafts=ROOT/'tools/typed72/drafts'
names=('cold_catalog.h','cold_card_fields.h','cold_catalog.cpp','cold_catalog_data.cpp','cold_catalog_probe.cpp','v_cold_catalog_probe.cpp',
       'cold_placement_rules.h','cold_placement_rules.cpp')
paths=[drafts/n for n in names]+[ROOT/'src/sim/typed/field.h',Path(__file__).resolve(),
       ROOT/'test_results/cold-catalog-work/v-export-v1.json',ROOT/'test_results/cold-catalog-work/generation-v1.json']
pins={str(p):evidence_store.sha256_file(p) for p in paths}
for p in paths:evidence_store.freeze_file(p,frozen/p.relative_to(ROOT),expected_sha256=pins[str(p)])
prior=ROOT/'build/typed72-v-cold-catalog-v1'
old=json.loads((prior/'build-report.json').read_text(encoding='utf8'))
base=Path(old['frozen'])
assert not old['frozen_drift']
headers=[base/'src',base/'third_party',base/'third_party/SDL2-2.30.9/include']
libs=[base/'build/Release'/n for n in ('pvzcore.lib','pvzui.lib','pvzsnapshot_zlib.lib')]
sdls=[base/'third_party'/name/'lib/x64' for name in ('SDL2-2.30.9','SDL2_image-2.8.2','SDL2_ttf-2.22.0','SDL2_mixer-2.8.0')]
sdl_names=('SDL2','SDL2_image','SDL2_ttf','SDL2_mixer')
libs+=[d/(n+'.lib') for d,n in zip(sdls,sdl_names)]
src=frozen/'tools/typed72/drafts'
q=lambda p:'"'+p.as_posix()+'"'
cmake='cmake_minimum_required(VERSION 3.20)\nproject(Typed72ColdCatalog LANGUAGES CXX)\nset(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)\n'
cmake+='add_executable(cold_catalog_probe '+ ' '.join(q(src/n) for n in ('cold_catalog.cpp','cold_catalog_data.cpp','cold_catalog_probe.cpp','cold_placement_rules.cpp'))+')\n'
cmake+='target_include_directories(cold_catalog_probe PRIVATE '+q(frozen/'src')+' '+q(base/'src')+' '+q(base/'third_party')+')\n'
cmake+='add_executable(v_cold_catalog_probe '+q(src/'v_cold_catalog_probe.cpp')+')\n'
cmake+='target_include_directories(v_cold_catalog_probe PRIVATE '+' '.join(map(q,headers))+')\n'
cmake+='target_link_libraries(v_cold_catalog_probe PRIVATE '+' '.join(map(q,libs))+' ws2_32)\n'
cmake+='foreach(t cold_catalog_probe v_cold_catalog_probe)\n target_compile_features(${t} PRIVATE cxx_std_20)\n'
cmake+=' target_compile_options(${t} PRIVATE /utf-8 /fp:precise /MP1 /bigobj)\n target_compile_definitions(${t} PRIVATE SDL_MAIN_HANDLED NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)\nendforeach()\n'
(stage/'CMakeLists.txt').write_text(cmake,encoding='utf8')
report=dict(pinned=pins,referenced_v_closure=str(prior/'build-report.json'),referenced_v_closure_sha256=evidence_store.sha256_file(prior/'build-report.json'),
            runtime_workdir=str(base),library_provenance=old['library_provenance'],cmake_sha256=evidence_store.sha256_file(stage/'CMakeLists.txt'))
(stage/'build-inputs.json').write_text(json.dumps(report,indent=2),encoding='utf8')
cmake_exe=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
env=dict(os.environ,_CL_='/MP1 /FS')
for name,args in (('configure',['-S',str(stage),'-B',str(stage/'build'),'-G','Visual Studio 17 2022','-A','x64']),
                  ('build',['--build',str(stage/'build'),'--config','Release','--parallel','1'])):
    with (stage/(name+'.log')).open('wb') as log:subprocess.run([cmake_exe]+args,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
for directory,name in zip(sdls,sdl_names):
    original=ROOT/(directory/(name+'.dll')).relative_to(base)
    evidence_store.freeze_file(original,stage/'build/Release'/original.name,expected_sha256=old['pinned'][str(original)])
report['source_drift']=[p for p,h in pins.items() if evidence_store.sha256_file(p)!=h]
report['exe_sha256']={n:evidence_store.sha256_file(stage/'build/Release'/(n+'.exe')) for n in ('cold_catalog_probe','v_cold_catalog_probe')}
(stage/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
assert not report['source_drift']
print(json.dumps(dict(stage=str(stage),exe_sha256=report['exe_sha256'])))
