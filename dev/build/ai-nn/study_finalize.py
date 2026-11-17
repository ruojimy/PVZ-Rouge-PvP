"""Post-study held-out imitation metrics, inference cost and clustered statistics."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
import torch
from train import batches, OFFSETS
from study_train import from_export, read_data, score

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text('utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument('--study', type=Path, required=True)
args = ap.parse_args()
base = args.study.resolve()
assert read(base/'run.json')['completed']
assert (base/'challenger-strength.json').exists()
assert not (base/'final-analysis.json').exists()
torch.set_num_threads(2)
binary = HERE/'windows-20261116/Release'
subprocess.run([sys.executable,'-X','utf8',str(HERE/'prepare_training.py'),
    '--records',str(base/'test-r22/matches'),'--ids',str(base/'test-ids.txt'),
    '--encoder',str(binary/'neural_dataset.exe'),'--out',str(base/'test-dataset.jsonl'),'--stride','4'],check=True)
header, rows = read_data(base/'test-dataset.jsonl')
plan = read(base/'plan.json')
models = {'original':Path(plan['original_model']),
          'compact':base/'training/compact/model.json','wide':base/'training/wide/model.json'}
metrics = {}
for name,path in models.items():
    meta, model = from_export(path)
    assert all(meta[k]==header[k] for k in ('sim_fingerprint','behaviors','catalog_hash','rules_hash'))
    model.eval()
    metrics[name] = score(model, rows)
    # The save head is disabled in C++; its untrained logits are not policy errors.
    for field in ('loss','exact_plan_heads','exact_plan_heads_rate'):
        metrics[name].pop(field,None)
    metrics[name]['heads'].pop('zombie_save',None)
    correct=total=0
    with torch.no_grad():
        for x,side,y in batches(rows,256):
            logits=model(*x)
            valid=torch.ones(len(y),dtype=torch.bool)
            for h in range(3):
                mask=side if h<2 else ~side
                valid &= (logits[:,OFFSETS[h]:OFFSETS[h+1]].argmax(1)==y[:,h]) | ~mask
            correct+=int(valid.sum());total+=len(y)
    metrics[name]['active_plan_accuracy']=correct/total
    metrics[name]['enabled_heads']=[True,True,True,False]
    metrics[name]['model_sha256']=sha(path)

# Same observations for every inference-cost arm, spanning each map's unit counts.
groups={}
with (base/'test-dataset.jsonl').open(encoding='utf-8') as source:
    feature_header=json.loads(next(source))
    for line in source:
        row=json.loads(line);groups.setdefault(row['map'],[]).append(row)
chosen=[]
for key,group in sorted(groups.items()):
    group.sort(key=lambda r:len(r['x']['own'])+len(r['x']['enemy']))
    chosen.extend(group[i] for i in np.linspace(0,len(group)-1,min(16,len(group)),dtype=int))
bench_data=base/'benchmark-states.jsonl'
with bench_data.open('w',encoding='utf-8',newline='\n') as out:
    for row in [feature_header,*chosen]:out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
with (base/'inference-benchmark.json').open('wb') as output:
    subprocess.run([str(binary/'neural_benchmark.exe'),str(bench_data),*[str(p) for p in models.values()]],
                   stdout=output,check=True)

baseline=read(base/'test-r22/summary.json')
selection=read(base/'selection.json')['selected']
challengers=read(base/'challenger-strength.json')
strength=read(base/'strength.json')['comparisons']
comparisons={}
def attach(key, old, new, seat, comparison):
    blocks={}
    for uid in baseline['ids']:
        a,b=old['matches'][uid],new['matches'].get(uid)
        win=lambda r:bool(r and r['winner']==seat and not r['timeout'] and not r['ai_error'])
        blocks.setdefault(a['map'],[]).append(int(win(b))-int(win(a)))
    sums=np.array([sum(x) for x in blocks.values()]);sizes=np.array([len(x) for x in blocks.values()])
    rng=np.random.default_rng(161116);picked=rng.integers(0,len(blocks),(20000,len(blocks)))
    rates=sums[picked].sum(1)/sizes[picked].sum(1)
    comparisons[key]=dict(comparison,paired_win_rate_difference=float(sums.sum()/sizes.sum()),
        map_block_bootstrap_ci95=np.quantile(rates,[.025,.975]).tolist(),map_blocks=len(blocks))
for seat in ('plant','zombie'):
    old=read(base/f'test-original-{seat}/summary.json')
    name=selection[seat]['name']
    selected=baseline if name=='r22' else old if name=='original' else read(base/f'test-selected-{seat}/summary.json')
    trained=read(Path(challengers[seat]['summary_path']))
    attach('selected-'+seat,baseline,selected,seat,strength['selected-'+seat])
    attach('selected-vs-original-'+seat,old,selected,seat,strength['selected-vs-original-'+seat])
    attach('trained-'+seat,baseline,trained,seat,challengers[seat]['vs_r22'])
    attach('trained-vs-original-'+seat,old,trained,seat,challengers[seat]['vs_original'])
ordered=sorted((v['paired_exact_p'],k) for k,v in comparisons.items());adjusted=0.0
for rank,(p,key) in enumerate(ordered):
    adjusted=max(adjusted,min(1.0,p*(len(ordered)-rank)))
    row=comparisons[key]
    row['paired_p_holm_8']=adjusted
    row['improvement_supported_after_multiplicity']=bool(adjusted<.05 and row['gains']>row['losses'] and
                                                       not row['crashed'] and not row['ai_errors'])
report=dict(format='pvz-ai-study-final-1',heldout_imitation=metrics,paired_strength=comparisons,
    inference=read(base/'inference-benchmark.json'),trained_challengers={k:v['name'] for k,v in challengers.items()},
    selected_policy=selection,holdout_ids=baseline['ids'],
    limitations=['Known maps, new seed/deck openings; not unseen-map generalization.',
        '24 paired games per seat, clustered in 12 maps and shared seeds; bootstrap only groups maps.',
        '600-second match cap; timeout/crash/AI error always stays in the denominator.',
        'The neural planner controls three strategic heads; r22 still owns movement, placement and other decisions.',
        'Absolute economy output cannot express 11; the neutral residual contract preserves 11. No deployment change.',
        'Fixed residual-minus1 is a constant strategy candidate, not reward-trained neural reinforcement learning.',
        'The two architectures have four matched from-scratch candidates each; compact also has two separately identified warm starts.',
        'Inference benchmark spans 16 unit-count quantiles per map; timings are not population-weighted gameplay measurements.'])
(base/'final-analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(dict(test_samples=len(rows),models={k:{h:round(v['heads'][h]['accuracy'],5)
    for h in ('econ_goal','plant_mode','grave_goal')} for k,v in metrics.items()},
    challengers=report['trained_challengers']),ensure_ascii=False))
