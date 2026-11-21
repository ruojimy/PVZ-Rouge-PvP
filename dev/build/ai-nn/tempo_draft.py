"""Draft extra home-only batches with the release's native lobby adviser."""
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from tempo_pool import *

def generate():
    source=R/'build/pvp73-tools';dest=OUT/'draft-src';dest.mkdir(exist_ok=True)
    s=(source/'deck73_corpus.cpp').read_text('utf8')
    token='for(const auto& map:maps)for(int night='
    assert s.count(token)==1
    (dest/'deck73_corpus.cpp').write_text(s.replace(token,'for(const auto& map:maps)if(map=="家院")for(int night='),'utf8')
    c=(source/'CMakeLists.txt').read_text('utf8').split('# Compile the current scenario')[0]
    (dest/'CMakeLists.txt').write_text(c.replace('foreach(n ref73_record cold73_export v_cold_catalog_probe deck73_corpus)','foreach(n deck73_corpus)'),'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'home-draft','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'home-draft','--config','Release','--parallel',2)
    exe=OUT/'home-draft/Release/deck73_corpus.exe'
    env={**os.environ,'PATH':str(EXPORT)+os.pathsep+os.environ['PATH']}
    def one(n):
        raw=OUT/f'home-only-{n}.tmp';final=OUT/f'draft-{n}.json'
        if final.exists():return
        subprocess.run([str(x) for x in (exe,raw,3,16,4210000+n*10000,79395+291*n)],cwd=R,env=env,check=True)
        rows=read(raw);assert len(rows)==96 and all(r.get('map')=='家院' for r in rows)
        # Exclusive publication keeps concurrent native batches independent.
        try:os.link(raw,final)
        except FileExistsError:pass
        raw.unlink()
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(one,range(4,7)))
    fixed(OUT/'draft-build.json',dict(source=sha(dest/'deck73_corpus.cpp'),original=sha(source/'deck73_corpus.cpp'),binary=sha(exe),batches=[4,5,6]))
