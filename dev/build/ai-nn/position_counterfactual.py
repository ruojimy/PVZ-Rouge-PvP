"""Single-decision interventions on the first eligible unseen home deck openings."""
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from position_study import OUT,MODELS,BASE,BUILD,BIN,sha,read,write,cmd,score
from position_build import replace_once
from overnight_eval import footer


def build():
    original=OUT/'native-src';root=OUT/'fork-src';root.mkdir(exist_ok=True)
    code=(original/'position_head.h').read_text('utf-8-sig')
    code=replace_once(code,'inline bool active=false;', '''inline bool active=false;
inline ainn::J intervention=nullptr;
inline bool fork_now(const char* kind,double t){
    const char* k=std::getenv("PVZ_POSITION_FORK_KIND");const char* when=std::getenv("PVZ_POSITION_FORK_T");
    return intervention.is_null()&&k&&when&&std::string(k)==kind&&std::abs(t-std::stod(when))<1e-5;
}''')
    code=replace_once(code,'for(const auto& a:list){\n                    if(a.kind==wait)', '''const bool suppress_approach=fork_now("approach",v.time);
                if(suppress_approach)intervention={{"kind","approach"},{"t",v.time},{"action","remove travel for this decision"}};
                for(const auto& proposal:list){
                    auto a=proposal;
                    if(suppress_approach&&a.kind==approach)continue;
                    if(a.kind==wait)''')
    code=replace_once(code,'const double facing=b.dx(a.x,b.foe.x)>=0?1.:-1.;','''std::optional<std::string> actual_source=src;
                    ainn::J edit=nullptr;
                    if(a.kind==spawn&&fork_now("source",v.time)&&hint.card==a.card&&!hint.source.empty()&&hint.source!=a.source){
                        for(const auto* g:b.graves)if(g->id==hint.source&&service.preview(a.card,g->x,g->y-24.,g->id,false).empty()){
                            edit={{"kind","source"},{"t",v.time},{"from",a.source},{"to",g->id},{"card",a.card},
                                  {"from_xy",{a.x,a.y}},{"to_xy",{g->x,g->y-24.}}};
                            a.source=g->id;a.x=g->x;a.y=g->y-24.;actual_source=g->id;break;
                        }
                    }
                    const double facing=b.dx(a.x,b.foe.x)>=0?1.:-1.;''')
    code=replace_once(code,'if(src)args.emplace_back("grave",*src);','if(actual_source)args.emplace_back("grave",*actual_source);')
    code=replace_once(code,'record(b,a,hint,list.size(),legal);','if(!edit.is_null())intervention=edit;record(b,a,hint,list.size(),legal);')
    (root/'position_head.h').write_text(code,'utf8')
    runner=(original/'position_match.cpp').read_text('utf8')
    runner=replace_once(runner,'footer["accepted_commands"]=std::move(commands);','footer["accepted_commands"]=std::move(commands);footer["intervention"]=position_ai::intervention;')
    (root/'position_match.cpp').write_text(runner,'utf8')
    for name in ['tactical_session.cpp','CMakeLists.txt']:shutil.copyfile(original/name,root/name)
    exe=re.search('^CMAKE_COMMAND:INTERNAL=(.+)$',(BUILD/'CMakeCache.txt').read_text('utf8'),re.M).group(1)
    dest=OUT/'fork-build'
    cmd(exe,'-S',root,'-B',dest,'-G','Visual Studio 17 2022','-A','x64')
    cmd(exe,'--build',dest,'--config','Release','--parallel',2)
    shutil.copy2(BIN/'SDL2.dll',dest/'Release/SDL2.dll')
    write(OUT/'fork-build.json',dict(binary=sha(dest/'Release/position_match.exe'),source=sha(root/'position_head.h')))


def run():
    root=OUT/'forks';root.mkdir(exist_ok=True)
    model=Path(read(OUT/'zombie-frozen.json')['model'])
    folder=OUT/'games/home-zombie-h-candidate/matches'
    meta=read(OUT/'generalization-plan.json')['per_opening']
    tasks=[]
    for kind,n in [('source',4),('approach',2)]:
        eligible=[]
        for uid in sorted(meta):
            if not meta[uid]['unseen_deck_pair']:continue
            trace=footer(folder/(uid+'.jsonl'))
            for event in trace['spatial_actions']:
                if (kind=='approach' and event['kind']=='approach') or (kind=='source' and event['kind']=='spawn' and event['preview_legal_exits']>=2 and event['native_card']==event['card'] and event['native_source'] and event['native_source']!=event['source']):
                    eligible.append((uid,kind,event['t']))
                    break
        tasks.extend(eligible[:n])
    def fork(task):
        uid,kind,t=task
        f=root/(uid+'-'+kind+'.jsonl')
        if not f.exists():
            args=[OUT/'fork-build/Release/position_match.exe','--corpus',OUT/'plain','--id',uid,'--out',f,'--planner','nn',
                  '--model',MODELS['h'],'--zombie-model',BASE,'--nn-seat','both','--position-model',model,'--control-hz','15','--limit-seconds','600','--telemetry','--no-records']
            subprocess.run([str(a) for a in args],check=True,stdout=subprocess.DEVNULL,env=dict(os.environ,PVZ_POSITION_FORK_KIND=kind,PVZ_POSITION_FORK_T=str(t)))
        changed=footer(f);base=footer(folder/(uid+'.jsonl'))
        assert not changed['ai_error']
        for field,key in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')]:
            assert [v for v in changed[field] if v[key]<t-.001]==[v for v in base[field] if v[key]<t-.001]
        applied=changed['intervention']
        if applied is None:assert changed['log_sha256']==base['log_sha256']
        def ending(row):
            return dict(winner=(row['result'] or {}).get('winner'),time=row['time'],timeout=row['timeout'],battle=row['log_sha256'])
        return dict(id=uid,kind=kind,t=t,applied=applied,prefix_matched=True,trained=ending(base),intervened=ending(changed))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fork,tasks))
    write(OUT/'counterfactuals.json',dict(results=results,eligible_sample_count=len(tasks),
          interpretation='One decision changed; both actors then resume the same frozen policies. Small directed sample. No weight selection.'))

