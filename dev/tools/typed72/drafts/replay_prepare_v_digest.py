import hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
stage=ROOT/'build/typed72-room-stage/v-digest';stage.mkdir(exist_ok=True)
source=stage/'source';source.mkdir(exist_ok=True)
inputs=[]
for path in (ROOT/'src').rglob('*'):
    if not path.is_file() or path.suffix not in ('.h','.hpp','.inc'):continue
    dest=source/'src'/path.relative_to(ROOT/'src');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);inputs.append(dest)
shutil.copy2(ROOT/'tools/typed72/drafts/replay_v_digest_probe.cpp',stage/'replay_v_digest_probe.cpp')
libs=[ROOT/'build/Release'/name for name in ('pvzcore.lib','pvzui.lib','pvzsnapshot_zlib.lib')]
sdls=[ROOT/'third_party'/name/'lib/x64' for name in ('SDL2-2.30.9','SDL2_image-2.8.2','SDL2_ttf-2.22.0','SDL2_mixer-2.8.0')]
for d,n in zip(sdls,('SDL2','SDL2_image','SDL2_ttf','SDL2_mixer')):libs.append(d/(n+'.lib'))
cmake='''cmake_minimum_required(VERSION 3.20)
project(RoomVDigest LANGUAGES CXX)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
add_executable(replay_v_digest_probe replay_v_digest_probe.cpp)
target_compile_features(replay_v_digest_probe PRIVATE cxx_std_20)
target_compile_options(replay_v_digest_probe PRIVATE /utf-8 /fp:precise /MP1 /FS /bigobj)
target_compile_definitions(replay_v_digest_probe PRIVATE SDL_MAIN_HANDLED NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
'''
includes=[source/'src',ROOT/'third_party',ROOT/'third_party/SDL2-2.30.9/include']
cmake+='target_include_directories(replay_v_digest_probe PRIVATE '+' '.join('"'+p.as_posix()+'"' for p in includes)+')\n'
cmake+='target_link_libraries(replay_v_digest_probe PRIVATE '+' '.join('"'+p.as_posix()+'"' for p in libs)+' ws2_32)\n'
(stage/'CMakeLists.txt').write_text(cmake,encoding='utf8');inputs+=libs+[stage/'CMakeLists.txt',stage/'replay_v_digest_probe.cpp',Path(__file__).resolve()]
for path in (ROOT/'third_party/nlohmann').rglob('*'):
    if path.is_file():inputs.append(path)
for path in (ROOT/'third_party/SDL2-2.30.9/include').rglob('*'):
    if path.is_file():inputs.append(path)
pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs};(stage/'build-inputs.json').write_text(json.dumps(pins,indent=2),encoding='utf8')
tool='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe';env=dict(os.environ,_CL_='/MP1 /FS')
with (stage/'configure.log').open('wb') as log:subprocess.run([tool,'-S',str(stage),'-B',str(stage/'build'),'-G','Visual Studio 17 2022','-A','x64'],stdout=log,stderr=subprocess.STDOUT,check=True,env=env,timeout=180)
with (stage/'build.log').open('wb') as log:subprocess.run([tool,'--build',str(stage/'build'),'--config','Release','--parallel','1'],stdout=log,stderr=subprocess.STDOUT,check=True,env=env,timeout=600)
for d,n in zip(sdls,('SDL2','SDL2_image','SDL2_ttf','SDL2_mixer')):shutil.copy2(d/(n+'.dll'),stage/'build/Release'/(n+'.dll'))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in pins.items())
print('Direct old-V JSON and catalog.digest probe built; not yet tested.')
