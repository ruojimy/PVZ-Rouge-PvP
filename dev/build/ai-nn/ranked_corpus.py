"""Ranked-seven native cold export with a shared immutable simulation pixel atlas."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import os
from pathlib import Path
import subprocess
import tempfile

from ranked_draft import *
from league_data import OLD_CORPUS, sha

EXPORTER=ROOM.with_name('cold73_export.exe')

@lru_cache(None)
def atlas():
    i=read(OLD_CORPUS/'index.json');p=OLD_CORPUS/i['atlas']
    assert sha(p)==i['atlas_sha256']
    return p

def native(sc, directory, name, full=False, original=False):
    check_game(sc)
    src=directory/(name+'.input.json');cold=directory/(name+'.json');draw=directory/(name+'.draw.json')
    write(src,sc)
    args=[(EXPORT/'cold73_export.exe') if original and not PROFILE else EXPORTER,src,cold]
    if full:args.append(directory/'atlas.bin')
    else:args.extend(['--draw-only',draw])
    result=subprocess.run(args,cwd=DATA_ROOT,capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf8','replace'))
    src.unlink()
    data=read(cold)
    assert data['seed']==sc['seed'] and all(data['battle']['rules'][k]==v for k,v in RULES.items())
    if PROFILE:assert data['battle']['rules']['build']==PROFILE['version']
    assert data['battle']['bans']==sc['bans']
    for s in SIDES:assert data['players'][s]['deck']==sc['decks'][s]
    return cold, (directory/'atlas.bin.draw.json') if full else draw

def canonical_draw(d):
    seen={}
    for part in ('world','ui','world_before'):
        for key,entry in sorted(d[part].items()):
            if isinstance(entry,dict) and 'id' in entry:
                entry['id']=seen.setdefault(str(entry['id']),len(seen))
    return d

def verify(sc):
    with tempfile.TemporaryDirectory(dir=RUN) as temp:
        p=Path(temp)
        a,ad=native(sc,p,'reference',full=True,original=True)
        b,bd=native(sc,p,'candidate')
        assert sha(p/'atlas.bin')==sha(atlas())
        assert read(a)==read(b)
        assert canonical_draw(read(ad))==canonical_draw(read(bd))
        return dict(exporter=sha(EXPORTER),reference=sha(EXPORTER if PROFILE else EXPORT/'cold73_export.exe'),room=sha(ROOM),
                    simulation_atlas=sha(atlas()),cold=sha(a),identical_cold=True,identical_draw_aliases=True)

def create(directory,scenarios,jobs=1):
    directory.mkdir(exist_ok=True,parents=True)
    def one(item):
        i,sc=item;uid=f'{i:03d}';cold,draw=native(sc,directory,uid)
        return dict(**sc,id=uid,cold=cold.name,draw=draw.name,cold_sha256=sha(cold),draw_sha256=sha(draw))
    with ThreadPoolExecutor(jobs) as pool:entries=list(pool.map(one,enumerate(scenarios)))
    write(directory/'index.json',dict(entries=entries,atlas=Path(os.path.relpath(atlas(),directory)).as_posix()))
    return entries
