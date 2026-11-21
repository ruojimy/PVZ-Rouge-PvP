"""Paired continuations from the first native command disagreement, on home maps."""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from event_study import OUT as PREVIOUS, ROOT, R, H, BUILD, EXPORT, OLD_Z, PROGRAM, PARENT, STRONG, PLANTS, deck, fixed, inputs_ok, read, sha, cmd
from position_build import replace_once
from option_study import size, LIMIT, RESERVE, FREE_FLOOR, PREV,NIGHT,PRIOR_HOME,PRIOR,kill_owned,write

OUT=ROOT/'switch'
CORPUS=OUT/'plain'
NATIVE=OUT/'native/Release/position_match.exe'
EVENT=Path(read(PREVIOUS/'zombie-selected.json')['path'])
OLD_CORPUS=PREVIOUS/'plain'
DEPLOY=OUT/'live/Release/position_match.exe'
WALK=OUT/'walk/Release/position_match.exe'
ARRIVAL=OUT/'arrival/Release/position_match.exe'
CONTEXT=OUT/'context/Release/position_match.exe'

def setup():
    inputs_ok()
    for p in (OUT,OUT/'temp',OUT/'models'):p.mkdir(exist_ok=True)
    assert sha(EVENT)==read(PREVIOUS/'zombie-selected.json')['model']
    fixed(OUT/'plan.json',dict(z16=sha(PARENT),event=sha(EVENT),plant=sha(STRONG),
        review='All 11 old wins lost. Compare every zombie command at every native tick. Reconstruct the two original continuations, and also switch from the z16 controller at that same state.',
        training='Freeze plant-1p, historical plant O and r22. Balance loss of old wins with actual wins gained. Compare z16, event continuation, and moving to a legal forward site then trying to build there. No movement reward. Use grouped openings and keep fresh validation and both blind cohorts outside fitting.',
        test='Two fresh day/night balanced home cohorts versus r22,H,B. Prioritize preservation of original wins and losses converted to real wins. Check deployment frequency for both sides on common windows, unfinished games separately, and extend loss to timeout through 1200.'))

def prepare():
    if (OUT/'splits.json').exists():
        assert sha(CORPUS/'index.json')==read(OUT/'splits.json')['corpus'];return
    paths=[R/v for v in read(PREVIOUS/'splits.json')['historical_indexes']]+[OLD_CORPUS/'index.json']
    known=[set(),set()];seeds=set()
    for path in paths:
        for r in read(path)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                seeds.add(r['seed'])
                for k,d in zip(known,deck(r)):k.add(d)
    rng=np.random.default_rng(917708);pool=[];held=[];dev=[]
    # Unplayed procedurally drafted rows may be used only after full novelty checks.
    for d in (PREVIOUS,ROOT/'advantage',ROOT/'confirm',ROOT):
        for p in sorted(d.glob('draft-*.json')):
            pool.extend(r for r in read(p) if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'))
    for n in range(16):
        p=OUT/f'draft-{n}.json'
        if not p.exists():cmd(EXPORT/'deck73_corpus.exe',p,3,16,3010000+10000*n,49433+119*n)
        pool.extend(r for r in read(p) if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'))
        for _ in range(120):
            used=[set(k) for k in known];held=[]
            for j in range(24):
                eligible=[r for r in pool if bool(r['night'])==bool(j%2) and all(d not in k for d,k in zip(deck(r),used))
                          and (j<12 or r['seed']>=3010000)]
                if not eligible:break
                r=eligible[rng.integers(len(eligible))];held.append(r)
                for k,d in zip(used,deck(r)):k.add(d)
            if len(held)==24:break
        if len(held)!=24:continue
        used=[{deck(r)[j] for r in held} for j in range(2)];dev=[]
        for j in range(16):
            eligible=[r for r in pool if bool(r['night'])==bool(j%2) and all(d not in k for d,k in zip(deck(r),used))]
            if not eligible:break
            r=eligible[rng.integers(len(eligible))];dev.append(r)
            for k,d in zip(used,deck(r)):k.add(d)
        if len(dev)==16:break
    assert len(dev)==16 and len(held)==24
    rows=dev+held;assert len({r['seed'] for r in rows})==40
    for j in range(2):
        assert len({deck(r)[j] for r in rows})==40 and not {deck(r)[j] for r in held}&known[j]
    fixed(OUT/'scenarios.json',rows)
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',CORPUS)
    entries=read(CORPUS/'index.json')['entries'];ids=[r['id'] for r in entries]
    assert [(r['seed'],deck(r)) for r in rows]==[(r['seed'],deck(r)) for r in entries]
    fixed(OUT/'splits.json',dict(train=ids[:8],val=ids[8:16],a=ids[16:28],b=ids[28:],corpus=sha(CORPUS/'index.json'),
        excluded=list(map(len,known)),indexes=[str(p.relative_to(R)) for p in paths]))

def guard(stage):
    # Background continuations can share stages. A Windows byte lock releases on
    # process exit and prevents two owners from writing the same match receipts.
    import msvcrt
    locks=OUT/'locks';locks.mkdir(parents=True,exist_ok=True)
    with (locks/(stage+'.lock')).open('a+b') as lock:
        if not lock.tell():lock.write(b'0');lock.flush()
        while True:
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:time.sleep(1)
        try:
            builds={'build':('build','native-src',NATIVE),'build-live':('live-build','live-src',DEPLOY),
                    'build-walk':('walk-build','walk-src',WALK),'build-arrival':('arrival-build','arrival-src',ARRIVAL),'build-context':('context-build','context-src',CONTEXT)}
            if stage in builds:
                label,source,exe=builds[stage];manifest=OUT/(label+'.json')
                if manifest.exists():
                    receipt=read(manifest);assert sha(exe)==receipt['binary']
                    for name,h in receipt['sources'].items():assert sha(OUT/source/name)==h
                    for name,h in receipt['libraries'].items():assert sha(BUILD/'Release'/name)==h
                    return
            if stage=='context-zombie' and (OUT/'final-zombie.json').exists():return
            if stage in ('positive','fresh','later','walk','ready','zombie','plant') and (OUT/(stage+'.json')).exists():
                if stage!='later' or (OUT/'walk.json').exists():return
            monitor(stage)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def monitor(stage):
    OUT.mkdir(exist_ok=True);temp=OUT/'temp';temp.mkdir(exist_ok=True)
    old=sum(size(d) for d in (PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR))
    disk=OUT/'disk.json'
    peak=read(disk)['peak'] if disk.exists() else old+size(ROOT)
    def check():
        nonlocal peak
        try:used=old+size(ROOT)
        except FileNotFoundError:used=old+size(ROOT)
        peak=max(peak,used,read(disk)['peak'] if disk.exists() else 0)
        write(disk,dict(current=used,peak=peak,prior=old,cap=LIMIT,reserve=RESERVE))
        if used>=LIMIT-RESERVE or shutil.disk_usage(OUT).free<FREE_FLOOR or (ROOT/'STOP').exists():raise RuntimeError('disk or stop guard')
    check()
    with (OUT/(stage+'.log')).open('ab') as log:
        env=dict(os.environ,TEMP=str(temp),TMP=str(temp),PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        job=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',stage],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        try:
            while job.poll() is None:check();time.sleep(2)
            check()
            if job.returncode:raise RuntimeError('See '+str(OUT/(stage+'.log')))
        except BaseException:
            kill_owned(job);raise

def build():
    parent=PREVIOUS/'live-src';dest=OUT/'native-src';dest.mkdir(exist_ok=True)
    receipt=read(PREVIOUS/'live-build.json')
    for name,h in receipt['sources'].items():
        assert sha(parent/name)==h
        shutil.copyfile(parent/name,dest/name)
    for name,h in receipt['libraries'].items():assert sha(BUILD/'Release'/name)==h
    shutil.copyfile(H/'switch_control.inc',dest/'switch_control.inc')
    def edit(name,pairs):
        p=dest/name;s=p.read_text('utf8')
        for old,new in pairs:s=replace_once(s,old,new)
        p.write_text(s,'utf8')
    edit('option_control.inc',[('inline int forced_option=-1;', '''inline ainn::J switch_policy=nullptr,switch_events=ainn::J::array();
inline int switch_force=-1;
inline double switch_after=0.;
inline bool full_inputs=false;
inline int forced_option=-1;'''),
        ('    if(file.empty())return;', '''    switch_policy=nullptr;switch_events=ainn::J::array();full_inputs=false;
    if(file.empty())return;'''),
        ('        load_event(option_policy);','''        if(option_policy.contains("switch")){
            switch_policy=option_policy.at("switch");switch_force=forced;switch_after=after;forced_option=-1;
            full_inputs=switch_policy.value("full_inputs",false);
        }
        load_event(option_policy);''')])
    edit('tactical_session.cpp',[('if(position_ai::event_enabled)position_ai::native_price','if(position_ai::event_enabled||!position_ai::switch_policy.is_null())position_ai::native_price')])
    edit('position_match.cpp',[('if(kind=="rally"||kind=="deploy"','if(position_ai::full_inputs||kind=="rally"||kind=="deploy"'),
        ('footer["options"]=position_ai::option_events;', 'footer["options"]=position_ai::option_events;footer["switches"]=position_ai::switch_events;')])
    edit('position_head.h',[
        ('class Tactics {','#include "switch_control.inc"\nclass Tactics {\n    SwitchControl switching;'),
        ('        const bool arrived=', '''        const bool wrapped=!switch_policy.is_null();
        if(wrapped)switching.begin(v);
        const bool arrived='''),
        ('const int mask=event_enabled?event_choices.changes(v,service):0;', '''const int observed=(wrapped||event_enabled)?event_choices.changes(v,service):0;
        const int mask=event_enabled?observed:0;
        const bool examine=wrapped&&switching.examine(v.time,observed);'''),
        ('if(at_order||flag_due){','if(at_order||flag_due||examine||switching.traveling()){'),
        ('            if(at_order){\n                next_action=v.time+1.;std::vector<Action> list', '''            if(at_order||examine||switching.traveling()){
                auto candidates=[&](){std::vector<Action> list'''),
        ('                if(event_enabled){\n                    event_choices.choose(list,b,service,hint,mask,jump_at);', '''                return list;};
                auto list=candidates();
                const bool was_event=event_enabled;
                const int choice=examine?switching.decide(list,b,service,observed):-1;
                if(event_enabled!=was_event)list=candidates();
                if(at_order||(!was_event&&event_enabled)||switching.traveling()){
                next_action=v.time+1.;
                if(switching.traveling()){
                    list={switching.next(b,service,choice==3)};
                }else if(event_enabled){
                    event_choices.choose(list,b,service,hint,observed,jump_at);'''),
        ('                    options.accepted(b,a);','                    if(!wrapped||!event_enabled)options.accepted(b,a);\n                    switching.accepted(b,a);'),
        ('            if(flag_due){','            }\n            if(flag_due){')])
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'native','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'native','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',NATIVE.parent/'SDL2.dll')
    fixed(OUT/'build.json',dict(binary=sha(NATIVE),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))

def build_live():
    base=OUT/'native-src';dest=OUT/'live-src';dest.mkdir(exist_ok=True)
    receipt=read(OUT/'build.json')
    for name,h in receipt['sources'].items():
        assert sha(base/name)==h
        shutil.copyfile(base/name,dest/name)
    shutil.copyfile(H/'switch_reconsider.inc',dest/'switch_reconsider.inc')
    path=dest/'switch_control.inc';s=path.read_text('utf8')
    s=replace_once(s,'||(!handed && mask && switch_policy.contains("gate"))','||(mask && switch_policy.contains("gate") && (!handed||switch_policy.value("adaptive",false)))')
    s=replace_once(s,'    int decide(', '    #include "switch_reconsider.inc"\n    int decide(')
    s=replace_once(s,'        auto wanted=', '        if(handed&&!fork&&switch_policy.value("adaptive",false))return reconsider(list,b,svc,mask);\n        auto wanted=')
    path.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'live','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'live','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',DEPLOY.parent/'SDL2.dll')
    fixed(OUT/'live-build.json',dict(binary=sha(DEPLOY),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))

def build_walk():
    base=OUT/'native-src';dest=OUT/'walk-src';dest.mkdir(exist_ok=True)
    receipt=read(OUT/'build.json')
    for name,h in receipt['sources'].items():
        assert sha(base/name)==h
        shutil.copyfile(base/name,dest/name)
    path=dest/'switch_control.inc';s=path.read_text('utf8')
    s=replace_once(s,'    double deadline=', '    bool omit_build=false;\n    double deadline=')
    s=replace_once(s,'            route=*front;', '            omit_build=choice==4;route=*front;')
    s=replace_once(s,'                prior_graves.clear();','''                if(omit_build){
                    switch_events.push_back({{"phase","omit_build"},{"t",b.v.time},{"target",EventChoices::identity(a)},
                                             {"move_tiles",std::abs(b.dx(origin,b.me.x))}});
                    route.reset();return {wait,b.me.x,b.me.y};
                }
                prior_graves.clear();''')
    path.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'walk','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'walk','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',WALK.parent/'SDL2.dll')
    fixed(OUT/'walk-build.json',dict(binary=sha(WALK),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))

def build_arrival():
    base=OUT/'live-src';dest=OUT/'arrival-src';dest.mkdir(exist_ok=True)
    receipt=read(OUT/'live-build.json')
    for name,h in receipt['sources'].items():
        assert sha(base/name)==h
        shutil.copyfile(base/name,dest/name)
    p=dest/'switch_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'    double deadline=', '    std::vector<double> route_features; double route_start=0.;\n    double deadline=')
    s=replace_once(s,'            route=*front;', '            route_features=site;route_start=b.v.time;route=*front;')
    s=replace_once(s,'                prior_graves.clear();','''                if(!direct&&switch_policy.contains("arrival")){
                    auto x=route_features;
                    x.push_back(std::tanh((b.v.time-route_start)/5.));
                    x.push_back(std::tanh(std::abs(b.dx(origin,b.me.x))/8.));
                    const double gain=predict(x,switch_policy.at("arrival"));
                    const bool place=gain>=-switch_policy.at("arrival_margin").get<double>();
                    switch_events.push_back({{"phase","arrival_vote"},{"t",b.v.time},{"place",place},{"gain",gain},{"target",EventChoices::identity(a)}});
                    if(!place){route.reset();return {wait,b.me.x,b.me.y};}
                }
                prior_graves.clear();''')
    p.write_text(s,'utf8');p=dest/'switch_reconsider.inc';s=p.read_text('utf8')
    s=replace_once(s,'                route=*best;', '                route_features=features(b,mask,best);route_start=b.v.time;route=*best;')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'arrival','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'arrival','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',ARRIVAL.parent/'SDL2.dll')
    fixed(OUT/'arrival-build.json',dict(binary=sha(ARRIVAL),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))

def build_context():
    base=OUT/'arrival-src';dest=OUT/'context-src';dest.mkdir(exist_ok=True)
    receipt=read(OUT/'arrival-build.json')
    for name,h in receipt['sources'].items():
        assert sha(base/name)==h
        shutil.copyfile(base/name,dest/name)
    shutil.copyfile(H/'switch_context.inc',dest/'switch_context.inc')
    p=dest/'switch_control.inc';s=p.read_text('utf8')
    s=replace_once(s,'    // Compare the best legal forward', '    #include "switch_context.inc"\n    // Compare the best legal forward')
    s=replace_once(s,'        int choice=handed?', '        inspect_deck(b,svc);\n        int choice=handed?')
    s=replace_once(s,'q=predict(state,switch_policy.at("gate"));','q=switch_policy.contains("context")?contextual(state,site):predict(state,switch_policy.at("gate"));')
    s=replace_once(s,'            if(fork){','            ev["deck"]=initial_deck;\n            if(fork){')
    p.write_text(s,'utf8')
    cmake=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    cmd(cmake,'-S',dest,'-B',OUT/'context','-G','Visual Studio 17 2022','-A','x64')
    cmd(cmake,'--build',OUT/'context','--config','Release','--parallel',2)
    shutil.copyfile(BUILD/'Release/SDL2.dll',CONTEXT.parent/'SDL2.dll')
    fixed(OUT/'context-build.json',dict(binary=sha(CONTEXT),libraries=receipt['libraries'],sources={p.name:sha(p) for p in dest.iterdir()}))

if __name__=='__main__':
    if sys.argv[1]!='worker':guard(sys.argv[1])
    else:
        setup();stage=sys.argv[2]
        if stage=='prepare':prepare()
        elif stage=='build':build()
        elif stage=='build-live':build_live()
        elif stage=='build-walk':build_walk()
        elif stage=='build-arrival':build_arrival()
        elif stage=='build-context':build_context()
        else:
            from switch_fit import run
            run(stage)
