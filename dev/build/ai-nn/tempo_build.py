"""Add optional troop/grave history inputs to the frozen one-action controller."""
import re
import shutil
from tempo_pool import OUT,PREVIOUS,BUILD,H,read,fixed,sha,cmd
from position_build import replace_once

EXE=OUT/'native/Release/position_match.exe'

def build():
    receipt=read(PREVIOUS/'live-build.json')
    if (OUT/'build.json').exists():
        assert sha(EXE)==read(OUT/'build.json')['binary']
        return
    dest=OUT/'native-src';dest.mkdir(exist_ok=True)
    for name,h in receipt['sources'].items():
        p=PREVIOUS/'live-src'/name;assert sha(p)==h;shutil.copyfile(p,dest/name)
    shutil.copyfile(H/'tempo_features.inc',dest/'tempo_features.inc')
    p=dest/'single_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'    bool slice_pending=', '    #include "tempo_features.inc"\n    bool slice_pending=')
    assert s.count('        return x;')==2
    s=s.replace('        return x;','        append_tempo(x,b.v.time);\n        return x;')
    p.write_text(s,'utf8')
    p=dest/'switch_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'        if(a.kind==build||a.kind==spawn)last_deploy=b.v.time;', '''        if(a.kind==build||a.kind==spawn){
            last_deploy=b.v.time;
            if(tracks_tempo()){
                auto& ticks=a.kind==spawn?troop_ticks:grave_ticks;
                ticks.push_back(static_cast<int>(std::llround(b.v.time*30.)));
            }
        }''')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',EXE.parent/'SDL2.dll')
    fixed(OUT/'build.json',dict(binary=sha(EXE),sources={p.name:sha(p) for p in dest.iterdir()},libraries=receipt['libraries']))
