"""Fresh current-game openings and a predeclared two-stage imitation study."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
B=R/'test_results/ai-nn-dagger-20261117'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text('utf-8'))
assert not (B/'plan.json').exists()
tools=R/'build/pvp73-tools/ai-20261117/Release'
for dll in (R/'dist/PvZ-PvP-Native-20261117-pvp744-r3').glob('*.dll'):shutil.copy2(dll,tools/dll.name)
subprocess.run([str(tools/'deck73_corpus.exe'),str(B/'draft-pool.json'),'3','2','170000','171117'],cwd=R,check=True)
pool=read(B/'draft-pool.json');assert len(pool)==144
maps=list(dict.fromkeys(r['map'] for r in pool));chosen=[];entries=[]
for r in pool:
    group=(r['seed']-170000)//1000-1;variant=(r['seed']%500)//17
    if variant!=(maps.index(r['map'])+int(r['night'])+group)%2:continue
    assert not r.get('invalid') and not r.get('error')
    uid=f'{len(chosen):03d}';part=['train','validation','test'][group]
    chosen.append(r);entries.append(dict(id=uid,part=part,map=r['map'],night=r['night'],seed=r['seed'],ban_variant=variant))
assert len(chosen)==72
for part in ['train','validation','test']:
    ids=[x['id'] for x in entries if x['part']==part];assert len(ids)==24
    (B/(part+'-ids.txt')).write_text('\n'.join(ids)+'\n','utf-8')
(B/'scenarios.json').write_text(json.dumps(chosen,ensure_ascii=False,indent=2),'utf-8')
stage=R/'build/typed72-integrated-v44/source/src/sim/typed';app=R/'src/sim/typed72_app'
files=set(stage.glob('*.cpp'))|set(stage.glob('*.h'))|set(app.glob('*.h'))
for p in ['*.cpp','*.h','*.inc']:files.update((app/'composition').rglob(p))
for p in ['*.cpp','*.h']:files.update((app/'ai').rglob(p))
files.update(app/x for x in ['session.cpp','ai_planner_r22.cpp'])
source={p.relative_to(R).as_posix():sha(p) for p in files}
exe=R/'PVZ_rougePvP_native/PvZPvPNative.exe'
assert sha(exe)==sha(R/'dist/PvZ-PvP-Native-20261117-pvp744-r3/PvZPvPNative.exe')
plan=dict(game_revision='pvp744-r3',release_sha256=sha(exe),entries=entries,source_sha256=source,
    training='Two warm starts (old default and latest compact), 8/64 network, 28 global features, 27 outputs. '
    'Stage 0: 35 epochs max, patience 8, lr .0003. Stage 1: collect 12 training openings per seat with selected stage 0; '
    'query current r22 on each student state, add labelled data and fine-tune up to 25 epochs, patience 8, lr .0002. '
    'No reward optimization or self-play.',
    loss='Three active heads only. Mode loss x2; teacher mode transitions x3. Historical teacher rows .5; augmented rows .25; '
    'student-state relabels x2. Validation original rows only; remove identical validation features from training.',
    offline_selection='Minimum weighted active-head validation loss; freeze stage 1 before validation games.',
    promotion='Must pass tempo_gate versus r22 AND old default on both validation and sealed test: no fewer wins, '
    'no new timeout openings, no more timeouts, capped mean duration <=1.05. '
    'Also inspect common-window successful deployments and rich-idle time; passing outcome screen alone is not promotion.',
    evaluation='24 validation and 24 sealed test openings per seat; known maps/new seed groups; 600 game seconds, 15Hz, jobs4. '
    'The sole trained final candidate is tested even if validation gate fails, as research evidence, never automatic adoption.',
    training_sources='Historical observed teacher and student states are supplementary offline states, re-labelled with current r22. '
    'Fresh teacher and student games use latest production simulation. All previously observed openings are training-only.',
    seed=1744,new_seed_base=170000,draft_seed=171117)
(B/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf-8')
subprocess.run([sys.executable,'-X','utf8',str(H/'export_corpus.py'),str(B/'scenarios.json'),str(B/'corpus'),'4',str(tools/'cold73_export.exe')],check=True)
subprocess.run([sys.executable,'-X','utf8',str(H/'materialize_corpus.py'),str(B/'corpus'),str(B/'corpus-plain')],check=True)
print(json.dumps(dict(fresh_openings=72,plan_sha256=sha(B/'plan.json'))))
