"""Paired opening and opponent coverage study on the frozen native simulation."""
import collections
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from overnight_common import B as NIGHT, R, H, OLD, BIN, read, write, sha
from coverage_guard import OUT
from overnight_eval import screen

EXPORT = R/'build/pvp73-tools/ai-20261117/Release'
OLD_MODEL = OLD/'warm/old.json'
SIDES = ['plant','zombie']
LINEUPS = ['rr','or','ro','oo']
def cmd(*args):
    subprocess.run([str(a) for a in args],cwd=R,check=True)
def paths(name):
    return OUT/name
def inputs_ok():
    for k,v in read(NIGHT/'plan.json')['source_sha256'].items():
        assert sha(R/k)==v,k
    for k,v in read(NIGHT/'prepared.json')['binary_sha256'].items():
        assert sha(Path(k))==v,k
    formal=read(R/'dist/latest-native-release.json')
    assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==formal['exe_sha256']==read(NIGHT/'plan.json')['release_sha256']
def opening_key(sc):
    return sc['map'],sc['night'],sc['seed']
def prepare():
    inputs_ok()
    old_trajectories=read(NIGHT/'data/train.json')['sources']
    heads=[]
    for path in old_trajectories:
        with open(path,encoding='utf-8') as f: heads.append(json.loads(f.readline()))
    places={opening_key(sc) for sc in heads}
    trials=list((NIGHT/'residual/train-trials').glob('*.json'))
    write(OUT/'diagnosis.json',dict(previous_sources=len(heads),unique_training_openings=len(places),lineups=dict(collections.Counter(str(h['planners']) for h in heads)),residual_openings=len(read(NIGHT/'residual/plan.json')['training_ids']),residual_candidates=len(trials),no_changed_battle_log=sum(not read(p)['changed_training_ids'] for p in trials),switch_audit=str(NIGHT/'validation-error-audit.json'),prior_model_sha256=sha(OLD_MODEL)))
    configs=[('train',410000,27181,4),('validation',510000,27182,1),('test',610000,27183,1)]
    all_sc=[]; splits={}
    for split,seed,draft,variants in configs:
        path=OUT/(split+'-draft.json')
        cmd(EXPORT/'deck73_corpus.exe',path,1,max(2,variants),seed,draft)
        entries=read(path)
        maps=list(dict.fromkeys(s['map'] for s in entries))
        chosen=entries if variants==4 else [s for s in entries if (s['seed']%500)//17==(maps.index(s['map'])+int(s['night']))%2]
        assert len(chosen)==24*variants and all(not s.get('error') and not s.get('invalid') for s in chosen)
        splits[split]=[f'{i:03}' for i in range(len(all_sc),len(all_sc)+len(chosen))]
        all_sc+=chosen
    keys={opening_key(s) for s in all_sc}
    previous_sets=[OLD/'corpus-plain',NIGHT/'corpus-plain',NIGHT/'supplement/corpus-plain',NIGHT/'residual/corpus-plain']
    assert len(keys)==144 and all(not(keys & {opening_key(e) for e in read(p/'index.json')['entries']}) for p in previous_sets)
    write(OUT/'scenarios.json',all_sc)
    write(OUT/'plan.json',dict(splits=splits,scenarios_sha256=sha(OUT/'scenarios.json'),previous_release=read(NIGHT/'plan.json')['game_revision'],old_sha256=sha(OLD_MODEL),lineups=LINEUPS,train='96 fresh openings, four crossed lineups each, equal game weight. Fixed original mode and encoder. Train additive economy/grave logits from consistent game-level preferences, regularized toward the old model.',evaluation='24 validation and 24 sealed openings. Same opponent paired r22 and old references. No new timeout, no fewer wins, capped duration ratio <=1.0; common-window activity, both seats. Freeze one model before evaluation; run test even if validation fails for independent diagnosis.'))
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',4,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',OUT/'plain')
    assert len(read(OUT/'plain/index.json')['entries'])==144
def run_group(split,lineup,plant=None,zombie=None,records=False,ids=None):
    folder=OUT/split/lineup
    if (folder/'ready.json').exists():
        return folder
    ids=ids or read(OUT/'plan.json')['splits'][split]
    args=[sys.executable,H/'eval.py','--bin',BIN/'headless_match.exe','--corpus',OUT/'plain','--out-dir',folder,'--ids',','.join(ids),'--jobs','4','--limit-seconds','600']
    extra=['--telemetry']
    if not records: extra+=['--no-records']
    if plant or zombie:
        args+=['--planner','nn']
        extra+=['--model',plant or zombie,'--nn-seat','both' if plant and zombie else 'plant' if plant else 'zombie']
        if plant and zombie: extra+=['--zombie-model',zombie]
    if not (folder/'summary.json').exists():
        cmd(*args,'--',*extra)
    summary=read(folder/'summary.json')
    assert set(ids)==set(summary['matches']) and not summary['crashed'] and all(not m['ai_error'] for m in summary['matches'].values())
    if records:
        from coverage_extract import compact
        for uid in ids:
            compact(folder,uid)
    write(folder/'ready.json',dict(games=len(ids),summary_sha256=sha(folder/'summary.json')))
    return folder
def collect():
    inputs_ok()
    ids=read(OUT/'plan.json')['splits']['train']
    for i in range(0,len(ids),12):
        for lineup in LINEUPS:
            print('train',i,lineup,flush=True)
            run_group('train',f'{i:03}-{lineup}',OLD_MODEL if lineup[0]=='o' else None,OLD_MODEL if lineup[1]=='o' else None,True,ids[i:i+12])
def slim(a):
    return {k:v for k,v in a.items() if k!='activity'}
def evaluate(split):
    inputs_ok()
    model=OUT/'model/model.json'
    assert sha(model)==read(OUT/'frozen.json')['model_sha256']
    p={'o':OLD_MODEL,'r':None,'n':model}
    arms=LINEUPS+['nr','no','rn','on']
    for arm in arms:
        print(split,arm,flush=True)
        run_group(split,arm,p[arm[0]],p[arm[1]])
    results={}
    for idx,side in enumerate(SIDES):
        for opp in 'ro':
            def folder(policy):
                return OUT/split/(policy+opp if idx==0 else opp+policy)
            for ref in 'ro':
                a=screen(folder(ref),folder('n'),side)
                other=screen(folder(ref),folder('n'),SIDES[1-idx])
                g=a['outcome']
                a['other_side_activity_flags']=other['activity_flags']
                a['passed']=a['passed'] and not other['activity_flags'] and g['capped_mean_duration_ratio']<=1
                results[side+'-opp'+opp+'-ref'+ref]=slim(a)
    write(OUT/(split+'-results.json'),results)
if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='prepare': prepare()
    elif stage=='collect': collect()
    elif stage in ['validation','test']: evaluate(stage)
    elif stage=='fit':
        from coverage_fit import fit
        fit()
    else: raise ValueError(stage)
