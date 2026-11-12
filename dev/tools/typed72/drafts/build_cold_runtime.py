"""Rebuild a whole typed ABI closure, then add cold registration/placement."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/typed72'))
import evidence_store
ap=argparse.ArgumentParser();ap.add_argument('--stage',required=True,type=Path);a=ap.parse_args()
stage=a.stage.resolve()
if ROOT/'build' not in stage.parents:raise ValueError('stage outside build')
stage.mkdir(exist_ok=False)
draft=ROOT/'tools/typed72/drafts';previous=ROOT/'build/typed72-room-stage/source'
source=stage/'source';shutil.copytree(previous,source)
typed=source/'src/sim/typed'
names=('cold_card_fields.h','cold_catalog.h','cold_catalog.cpp','cold_catalog_data.cpp','cold_registration_state.h','cold_registration.h','cold_registration.cpp',
 'cold_deployment_state.h','cold_placement.h','cold_placement.cpp','cold_placement_rules.h','cold_placement_rules.cpp')
originals=[draft/n for n in names]+[draft/n for n in ('cold_registration_probe.cpp','v_cold_registration_probe.cpp','overlay_cold_registration.ps1','overlay_content_source.ps1')]+[Path(__file__).resolve()]
originals+=list((ROOT/'src/core').glob('*.h'))
pins={str(p):evidence_store.sha256_file(p) for p in originals}
for name in names:shutil.copy2(draft/name,typed/name)
for p in (ROOT/'src/core').glob('*.h'):shutil.copy2(p,source/'src/core'/p.name)
for script in ('overlay_content_source.ps1','overlay_cold_registration.ps1'):
 subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(draft/script),'-TypedDirectory',str(typed)],check=True)
for name in ('cold_registration_probe.cpp','v_cold_registration_probe.cpp'):shutil.copy2(draft/name,source/'tools/typed72'/name)
prior=ROOT/'build/typed72-v-cold-catalog-v1';old=json.loads((prior/'build-report.json').read_text(encoding='utf8'));base=Path(old['frozen'])
libs=[base/'build/Release'/n for n in ('pvzcore.lib','pvzui.lib','pvzsnapshot_zlib.lib')]
sdls=[base/'third_party'/n/'lib/x64' for n in ('SDL2-2.30.9','SDL2_image-2.8.2','SDL2_ttf-2.22.0','SDL2_mixer-2.8.0')];sdl_names=('SDL2','SDL2_image','SDL2_ttf','SDL2_mixer')
libs+=[d/(n+'.lib') for d,n in zip(sdls,sdl_names)]
q=lambda p:'"'+p.as_posix()+'"'
cmake=(typed/'CMakeLists.txt').read_text(encoding='utf8').replace(previous.as_posix(),source.as_posix())
cmake+='\ntarget_sources(pvztyped72 PRIVATE cold_catalog.cpp cold_catalog_data.cpp cold_registration.cpp cold_placement.cpp cold_placement_rules.cpp)\n'
cmake+='add_executable(cold_registration_probe '+q(source/'tools/typed72/cold_registration_probe.cpp')+')\ntarget_link_libraries(cold_registration_probe PRIVATE pvztyped72)\ntarget_include_directories(cold_registration_probe PRIVATE '+q(source/'third_party')+')\n'
cmake+='add_executable(v_cold_registration_probe '+q(source/'tools/typed72/v_cold_registration_probe.cpp')+')\ntarget_include_directories(v_cold_registration_probe PRIVATE '+' '.join(map(q,[base/'src',base/'third_party',base/'third_party/SDL2-2.30.9/include']))+')\n'
cmake+='target_link_libraries(v_cold_registration_probe PRIVATE '+' '.join(map(q,libs))+' ws2_32)\n'
cmake+='set_property(TARGET v_cold_registration_probe PROPERTY MSVC_RUNTIME_LIBRARY MultiThreaded)\ntarget_compile_features(v_cold_registration_probe PRIVATE cxx_std_20)\ntarget_compile_options(v_cold_registration_probe PRIVATE /utf-8 /fp:precise /MP1 /bigobj)\ntarget_compile_definitions(v_cold_registration_probe PRIVATE SDL_MAIN_HANDLED NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)\n'
(typed/'CMakeLists.txt').write_text(cmake,encoding='utf8')
closure={str(p):evidence_store.sha256_file(p) for p in source.rglob('*') if p.is_file()}
report=dict(pinned=pins,source=closure,referenced_v_closure=str(prior/'build-report.json'),referenced_v_closure_sha256=evidence_store.sha256_file(prior/'build-report.json'),runtime_workdir=str(base),library_provenance=old['library_provenance'])
(stage/'build-inputs.json').write_text(json.dumps(report,indent=2),encoding='utf8')
cmake_exe=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe';env=dict(os.environ,_CL_='/MP1 /FS')
for name,args in (('configure',['-S',str(typed),'-B',str(stage/'build'),'-G','Visual Studio 17 2022','-A','x64']),('build',['--build',str(stage/'build'),'--config','Release','--target','cold_registration_probe','v_cold_registration_probe','--parallel','1'])):
 with (stage/(name+'.log')).open('wb') as log:subprocess.run([cmake_exe]+args,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=1800)
for d,n in zip(sdls,sdl_names):
 original=ROOT/(d/(n+'.dll')).relative_to(base);evidence_store.freeze_file(original,stage/'build/Release'/original.name,expected_sha256=old['pinned'][str(original)])
report['changed_inputs']=[p for p,h in pins.items() if evidence_store.sha256_file(p)!=h];report['source_drift']=[p for p,h in closure.items() if evidence_store.sha256_file(p)!=h]
report['exe_sha256']={n:evidence_store.sha256_file(stage/'build/Release'/(n+'.exe')) for n in ('cold_registration_probe','v_cold_registration_probe')}
(stage/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
assert not report['source_drift'] and not report['changed_inputs']
print(json.dumps(dict(stage=str(stage),exe_sha256=report['exe_sha256'])))
