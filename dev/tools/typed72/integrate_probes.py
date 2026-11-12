"""Collect the probe sources actually used by each frozen stage into one flat tree.

Probes include each other by bare file name, so a same-directory stale copy
shadows the real one.  Later layers in LAYERS win; drafts is only a fallback
for probes never copied into a stage.  Every file records its origin.

    python integrate_probes.py --stage build/typed72-integrated-v3-probes2 --lib build/typed72-integrated-v3
"""
import argparse,hashlib,json,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LAYERS=[('draft',ROOT/'tools/typed72/drafts'),('tools',ROOT/'tools/typed72'),
    ('native-clock-v2',ROOT/'build/typed72-native-clock-v2'),('expansion-combat-v1',ROOT/'build/typed72-expansion-combat-v1'),
    ('expansion-combat-v2',ROOT/'build/typed72-expansion-combat-v2'),('room-stage',ROOT/'build/typed72-room-stage/source/tools/typed72'),
    ('cold-runtime-v2',ROOT/'build/typed72-cold-runtime-v2'),('content-v9',ROOT/'build/typed72-content-controller-v9'),('draft-newer',ROOT/'tools/typed72/drafts/_newer_than_stages')]
SKIP=('v_','native_art_probe')
CMAKE=r'''cmake_minimum_required(VERSION 3.20)
project(Typed72IntegratedProbes LANGUAGES CXX)
set(ROOT "@ROOT@")
set(LIBSTAGE "@LIB@")
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
add_library(typed_lib STATIC IMPORTED)
set_target_properties(typed_lib PROPERTIES IMPORTED_LOCATION "${LIBSTAGE}/build/Release/pvztyped72.lib")
file(GLOB PROBES "${CMAKE_CURRENT_SOURCE_DIR}/probes/*_probe.cpp")
foreach(src ${PROBES})
  get_filename_component(stem ${src} NAME_WE)
  string(REGEX REPLACE "_probe$" "72_probe" exe ${stem})
  add_executable(${exe} ${src})
  target_compile_features(${exe} PRIVATE cxx_std_20)
  target_compile_options(${exe} PRIVATE /utf-8 /fp:precise /W1 /MP1 /FS /bigobj)
  target_compile_definitions(${exe} PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS SDL_MAIN_HANDLED)
  target_include_directories(${exe} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/probes" "${LIBSTAGE}/source/src" "${ROOT}/src" "${ROOT}/third_party" "${ROOT}/third_party/SDL2-2.30.9/include")
  target_link_libraries(${exe} PRIVATE typed_lib "${ROOT}/third_party/SDL2-2.30.9/lib/x64/SDL2.lib" ws2_32)
endforeach()
'''
BUILD=r'''$stage=$PSScriptRoot
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$env:_CL_='/MP1 /FS'
& $cmake -S $stage -B "$stage/build" -G 'Visual Studio 17 2022' -A x64 *> "$stage/configure.log"; "cfg=$LASTEXITCODE"
$t=Get-Date
& $cmake --build "$stage/build" --config Release --parallel 2 -- /p:ContinueOnError=true *> "$stage/build.log"
"build=$LASTEXITCODE seconds=$([int]((Get-Date)-$t).TotalSeconds)"
"exes=" + (Get-ChildItem "$stage/build/Release" -Filter *.exe).Count
'''
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def collect(stage,lib):
    if stage.exists():raise SystemExit('stage exists: '+str(stage))
    probes=stage/'probes';probes.mkdir(parents=True);origin={};overrides={}
    for label,folder in LAYERS:
        if not folder.exists():continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix not in('.cpp','.inc','.h'):continue
            if path.suffix=='.cpp' and not path.name.endswith('_probe.cpp'):continue
            if path.suffix!='.cpp' and not path.name.endswith(('_fixture.inc','_fixture.h')):continue
            if path.name.startswith(SKIP):continue
            digest=sha(path)
            if path.name in origin and origin[path.name][1]!=digest:overrides.setdefault(path.name,[]).append(origin[path.name][0])
            shutil.copyfile(path,probes/path.name);origin[path.name]=(label,digest)
    (stage/'CMakeLists.txt').write_text(CMAKE.replace('@ROOT@',ROOT.as_posix()).replace('@LIB@',lib.as_posix()),encoding='utf8')
    (stage/'build.ps1').write_text(BUILD,encoding='utf8')
    (stage/'probe-manifest.json').write_text(json.dumps({'lib':lib.as_posix(),'files':{k:{'origin':v[0],'sha256':v[1],'shadowed':overrides.get(k,[])} for k,v in sorted(origin.items())}},indent=1,ensure_ascii=False),encoding='utf8')
    return origin,overrides
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True);parser.add_argument('--lib',required=True);args=parser.parse_args()
    origin,overrides=collect((ROOT/args.stage).resolve(),(ROOT/args.lib).resolve())
    counts={}
    for label,_ in origin.values():counts[label]=counts.get(label,0)+1
    print(json.dumps(counts),len(origin),'shadowed',len(overrides))
