"""Freeze and link an independent oracle to the retained current V libraries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
import evidence_store

def main():
    stage=ROOT/'build/typed72-v-cold-catalog-v1'
    stage.mkdir(exist_ok=False)
    frozen=stage/'frozen';frozen.mkdir()
    source=ROOT/'tools/typed72/drafts/v_cold_catalog_probe.cpp'
    libs=[ROOT/'build/Release'/name for name in ('pvzcore.lib','pvzui.lib','pvzsnapshot_zlib.lib')]
    sdls=[ROOT/'third_party'/name/'lib/x64' for name in ('SDL2-2.30.9','SDL2_image-2.8.2','SDL2_ttf-2.22.0','SDL2_mixer-2.8.0')]
    names=('SDL2','SDL2_image','SDL2_ttf','SDL2_mixer')
    sdl_libs=[directory/(name+'.lib') for directory,name in zip(sdls,names)]
    dlls=[directory/(name+'.dll') for directory,name in zip(sdls,names)]
    # Freeze the entire project header closure. CPP owners are retained as
    # source evidence, not falsely represented as the libraries' build inputs.
    paths=[p for p in (ROOT/'src').rglob('*') if p.is_file() and p.suffix in ('.h','.hpp','.inc')]
    paths += [p for p in (ROOT/'src/sim/pvp').rglob('*.cpp')]
    paths += [p for p in (ROOT/'third_party/SDL2-2.30.9/include').rglob('*') if p.is_file()]
    paths += [p for p in (ROOT/'third_party/nlohmann').rglob('*') if p.is_file()]
    paths += [p for p in (ROOT/'extract/data').rglob('*') if p.is_file()]
    paths += [ROOT/'extract/assets/index.json',source,Path(__file__).resolve(),Path(evidence_store.__file__).resolve()]+libs+sdl_libs+dlls
    paths=list(dict.fromkeys(paths));pins={}
    for path in paths:
        if not path.is_file():raise FileNotFoundError(str(path))
        digest=evidence_store.sha256_file(path);pins[str(path)]=digest
        evidence_store.freeze_file(path,frozen/path.relative_to(ROOT),expected_sha256=digest)
    include=[frozen/'src',frozen/'third_party',frozen/'third_party/SDL2-2.30.9/include']
    target='v_cold_catalog_probe'
    cmake='cmake_minimum_required(VERSION 3.20)\nproject(Typed72VColdCatalog LANGUAGES CXX)\n'
    cmake+='set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)\n'
    cmake+='add_executable('+target+' "'+(frozen/source.relative_to(ROOT)).as_posix()+'")\n'
    cmake+='target_compile_features('+target+' PRIVATE cxx_std_20)\n'
    cmake+='target_compile_options('+target+' PRIVATE /utf-8 /fp:precise /MP1 /bigobj)\n'
    cmake+='target_compile_definitions('+target+' PRIVATE SDL_MAIN_HANDLED NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)\n'
    cmake+='target_include_directories('+target+' PRIVATE '+' '.join('"'+p.as_posix()+'"' for p in include)+')\n'
    cmake+='target_link_libraries('+target+' PRIVATE '+' '.join('"'+(frozen/p.relative_to(ROOT)).as_posix()+'"' for p in libs+sdl_libs)+' ws2_32)\n'
    (stage/'CMakeLists.txt').write_text(cmake,encoding='utf8')
    report=dict(pinned=pins,frozen=str(frozen),library_provenance='Retained build/Release V libraries; source/library equivalence has not been re-established',
                runtime_workdir=str(frozen),header_closure='All src h/hpp/inc plus SDL/nlohmann headers',
                cmake_sha256=evidence_store.sha256_file(stage/'CMakeLists.txt'))
    (stage/'build-inputs.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    cmake_exe=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    env=dict(os.environ,_CL_='/MP1 /FS')
    with (stage/'configure.log').open('wb') as log:
        subprocess.run([cmake_exe,'-S',str(stage),'-B',str(stage/'build'),'-G','Visual Studio 17 2022','-A','x64'],stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=180)
    with (stage/'release-build.log').open('wb') as log:
        subprocess.run([cmake_exe,'--build',str(stage/'build'),'--config','Release','--parallel','1'],stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
    for path in dlls:evidence_store.freeze_file(path,stage/'build/Release'/path.name,expected_sha256=pins[str(path)])
    report['source_drift']=[path for path,digest in pins.items() if evidence_store.sha256_file(path)!=digest]
    report['frozen_drift']=[path for path,digest in pins.items() if evidence_store.sha256_file(frozen/Path(path).relative_to(ROOT))!=digest]
    report['exe_sha256']=evidence_store.sha256_file(stage/'build/Release'/ (target+'.exe'))
    (stage/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    assert not report['frozen_drift']
    print(json.dumps(dict(stage=str(stage),files=len(pins),source_drift=report['source_drift'],exe_sha256=report['exe_sha256'])))

if __name__=='__main__':main()
