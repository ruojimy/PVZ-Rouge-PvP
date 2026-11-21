"""Freeze new validation/test openings and the overnight disk/time protocol."""
import sys
from overnight_common import *
assert not (B/'plan.json').exists()
previous=read(OLD/'plan.json')
assert all(sha(R/p)==h for p,h in previous['source_sha256'].items())
assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==previous['release_sha256']
tools=R/'build/pvp73-tools/ai-20261117/Release'
command('draft',[tools/'deck73_corpus.exe',B/'draft.json','2','2','180000','181118'])
pool=read(B/'draft.json');maps=list(dict.fromkeys(r['map'] for r in pool));chosen=[];entries=[]
for r in pool:
    group=(r['seed']-180000)//1000-1;variant=(r['seed']%500)//17
    if variant!=(maps.index(r['map'])+int(r['night'])+group)%2:continue
    assert not r.get('invalid') and not r.get('error')
    uid=f'{len(chosen):03d}';part=['validation','test'][group]
    chosen.append(r);entries.append(dict(id=uid,part=part,map=r['map'],night=r['night'],seed=r['seed'],ban_variant=variant))
assert len(chosen)==48
write(B/'scenarios.json',chosen)
write(B/'plan.json',dict(game_revision='pvp744-r3',release_sha256=previous['release_sha256'],source_sha256=previous['source_sha256'],entries=entries,
    started_at=datetime.datetime.now(TZ).isoformat(),deadline='2026-11-18T09:00:00+08:00',fit_end='2026-11-18T08:20:00+08:00',
    storage=dict(max_new_bytes=LIMIT,safety_reserve=RESERVE,min_free_bytes=FREE_FLOOR,retention='Preserve historical evidence; reuse existing sources; compact evaluations; verify compressed new trajectories before deleting temporary originals.'),
    training='Policy-v2 12-way economy including 11; compare absolute and previous-mode-transition outputs. Warm-start current feature-v2 model. Critical-transition weighting and student-state re-labelling. No self-play reinforcement learning.',
    promotion='Per side versus r22 AND old default on validation and sealed test: no fewer wins, no more/new timeout openings, capped mean <=1.05; common-window deployment/resource flags block promotion.',
    testing='Known maps, new seed groups; 24 validation and 24 sealed test; do not change the selected weights after opening test. '
            'Select candidates on battle gates before imitation loss. If all fail validation, test only the best research candidate; do not promote it.',
    resources=dict(game_jobs=4,torch_threads=2),early_stop='Stop if time/disk safety triggers or repeated full rounds yield no useful progress.'))
command('export',[sys.executable,'-X','utf8',H/'export_corpus.py',B/'scenarios.json',B/'corpus','4',tools/'cold73_export.exe'])
command('materialize',[sys.executable,'-X','utf8',H/'materialize_corpus.py',B/'corpus',B/'corpus-plain'])
guard();print(json.dumps(dict(openings=48,plan_sha256=sha(B/'plan.json'))))
