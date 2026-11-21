"""Home study using one-decision interventions with frozen on-policy continuations."""
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path
import numpy as np
from option_study import ROOT,R,H,PRIOR,BUILD,EXPORT,PROGRAM,OLD_Z,inputs_ok,read,write,sha,cmd
from option_games import Game,MODELS,batch,trace,outcome,slow,extend
from position_build import replace_once

OUT=ROOT/'advantage'
CORPUS=OUT/'plain'
FORK=OUT/'native/Release/position_match.exe'
PARENT=Path(read(ROOT/'zombie-frozen.json')['model'])
STRONG=Path(read(ROOT/'plant-trial-frozen.json')['model'])
PLANTS={'r':None,'p':STRONG,'o':MODELS['o']}
OPPONENTS='rhb'

def game(i,plant,**kw):
    return Game(i,plant,storage=OUT,corpus=CORPUS,**kw)

def fixed(path,doc):
    if path.exists():assert read(path)==doc,path
    else:write(path,doc)

def setup():
    inputs_ok();OUT.mkdir(exist_ok=True);(OUT/'temp').mkdir(exist_ok=True)
    assert sha(STRONG)==read(ROOT/'plant-trial-frozen.json')['sha256']
    assert sha(PARENT)==read(ROOT/'zombie-frozen.json')['sha256']
    fixed(OUT/'design.json',dict(parent=sha(PARENT),plant=sha(STRONG),space=sha(OLD_Z),native=sha(PROGRAM),
        corpus='12 development and 8 validation home starts. Two preassigned 12-opening sealed cohorts; 24 fresh individual decks per seat, no historic deck on either side. Paired six day and six night per cohort.',
        zombie='Freeze r22, the latest plant candidate and historic O. Scan ordinary current-policy games. Intervene on exactly one decision and resume current policy on all routes. Keep diverse visited states, including high-confidence saving. Same digest and follow-up verification.',
        training='Compare centered return fitting and pairwise advantage fitting on identical on-policy labels. Count terminal results, use verified longer outcome as a fractional tiebreak for timeouts. Equal total weight per opening; group cross-validation. 22 inputs, 8 hidden units, 4 routes.',
        plant_update='Freeze selected zombie before perturbing the economic readout of the latest plant. Train against frozen zombie and validate against it and r22. Select challenger before testing; keep the incumbent on ties for adoption.',
        test='Both cohorts on r22,H,B for both seats, identical opening and opponent per comparison. Require positive net in each cohort, no losing opponent total per cohort, positive lower 95% clustered paired mean on combined cohorts and no bilateral-idle loss-to-timeout credit. Extend all matched losses becoming timeouts to 1200. No tuning on either cohort.'))

def deck(row):return tuple(tuple(sorted(row['decks'][s])) for s in ('plant','zombie'))

def prepare():
    setup()
    if (OUT/'splits.json').exists():
        assert sha(CORPUS/'index.json')==read(OUT/'splits.json')['corpus'];return
    known=[set(),set()];seeds=set()
    for p in [*(R/s for s in read(ROOT/'splits.json')['past_indexes']),ROOT/'plain/index.json',ROOT/'confirm/plain/index.json']:
        for e in read(p)['entries']:
            if e.get('map')=='家院' and 'decks' in e:
                seeds.add(e['seed'])
                for a,k in zip(deck(e),known):k.add(a)
    def rows(f):
        return [e for e in read(f) if e['map']=='家院' and e['seed'] not in seeds and not e.get('invalid') and not e.get('error')]
    old=[e for folder in (ROOT,ROOT/'confirm') for f in sorted(folder.glob('draft-*.json')) for e in rows(f)]
    def select(pool,used,count,seed):
        rng=np.random.default_rng(seed)
        for attempt in range(150):
            seen=[set(k) for k in used];selected=[];visited=set()
            for j in range(count):
                candidates=[r for r in pool if r['seed'] not in visited and r['night']==bool(j%2) and all(d not in k for d,k in zip(deck(r),seen))]
                if not candidates:break
                row=candidates[rng.integers(len(candidates))];selected.append(row);visited.add(row['seed'])
                for d,k in zip(deck(row),seen):k.add(d)
            if len(selected)==count:return selected,seen
        return [],used
    a,excluded=select(old,known,12,8043)
    new=[]
    for n in range(8):
        f=OUT/f'draft-{n}.json'
        if not f.exists():cmd(EXPORT/'deck73_corpus.exe',f,3,16,1910000+10000*n,93171+409*n)
        new.extend(rows(f))
        if not a:a,excluded=select(old+new,known,12,8043)
        b,used=select(new,excluded,12,7373)
        if a and b:break
    assert len(a)==len(b)==12
    reserved=[{deck(e)[j] for e in a+b} for j in range(2)]
    pool=[e for e in old+new if all(d not in k for d,k in zip(deck(e),reserved))]
    dev,_=select(pool,[set(),set()],20,4423)
    cases=dev+a+b
    assert len(dev)==20 and len({e['seed'] for e in cases})==44
    for j in range(2):
        assert len(reserved[j])==24 and not reserved[j]&(known[j]|{deck(e)[j] for e in dev})
    fixed(OUT/'scenarios.json',cases)
    if not (OUT/'corpus/index.json').exists():cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    if not (CORPUS/'index.json').exists():cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',CORPUS)
    entries=read(CORPUS/'index.json')['entries'];ids=[e['id'] for e in entries]
    assert [(e['seed'],deck(e)) for e in entries]==[(e['seed'],deck(e)) for e in cases]
    fixed(OUT/'splits.json',dict(train=ids[:12],validation=ids[12:20],a=ids[20:32],b=ids[32:],corpus=sha(CORPUS/'index.json'),excluded_decks=list(map(len,known))))

def build():
    setup()
    old=ROOT/'native-src';dest=OUT/'native-src';dest.mkdir(exist_ok=True)
    original=read(ROOT/'build.json');assert all(sha(old/f)==d for f,d in original['sources'].items())
    for p in old.iterdir():
        if p.is_file() and p.name!='option_control.inc':shutil.copyfile(p,dest/p.name)
    s=(old/'option_control.inc').read_text('utf8')
    s=replace_once(s,'(forced_option<0 || (option_events.empty() && t>=fork_after))','(forced_option<0 || !option_policy.is_null() || (option_events.empty() && t>=fork_after))')
    s=replace_once(s,'int chosen=forced_option;', '''const bool intervention=forced_option>=0 && (option_policy.is_null() ||
                    std::llround(30.*t)==std::llround(30.*fork_after));
                int chosen=intervention ? forced_option : -1;''')
    s=replace_once(s,'if(forced_option>=0)option_events.back()["prefix"]=option_prefix();','''if(intervention){
                    option_events.back()["prefix"]=option_prefix();
                    option_events.back()["forked"]=true;
                }''')
    (dest/'option_control.inc').write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',FORK.parent/'SDL2.dll')
    fixed(OUT/'build.json',dict(binary=sha(FORK),sources={p.name:sha(p) for p in dest.iterdir()},libraries=original['libraries']))

def run(stage):
    if stage=='prepare':prepare()
    elif stage=='build':build()
    else:
        from advantage_fit import run as execute
        execute(stage)
