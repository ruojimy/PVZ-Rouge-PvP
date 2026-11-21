"""Sequential frozen-opponent training on native home-map matches."""
import itertools
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from home_pool import OUT as PRIOR_HOME, CURRENT, PREV, OLD_MODEL, score, transitions, jointly_idle
from overnight_common import B as NIGHT, R, H, BUILD, BIN, LIMIT, RESERVE, FREE_FLOOR, read, write, sha, kill_owned
from coverage_study import EXPORT, inputs_ok, cmd
from coverage_guard import size
from overnight_eval import footer

OUT = R / 'test_results/ai-nn-home-position-20261118'
BASE = PRIOR_HOME / 'snapshot-only/model.json'
MODELS = {'r': None, 'o': OLD_MODEL, 'n': CURRENT, 'b': BASE,
          'a': PRIOR_HOME / 'r22-only/model.json', 'h': PRIOR_HOME / 'home-model/model.json'}
TOOL = OUT / 'native/Release/position_match.exe'


def same_opening_screen():
    raw = {}
    strength = {}
    pairs = {}
    for plant in 'onbah':
        traces = {}
        total = 0
        for opp in 'ron':
            rows = read(PRIOR_HOME / 'test' / (plant + opp) / 'ready.json')['rows']
            for uid, row in rows.items():
                assert sha(Path(row['trace'])) == row['match']['file_sha256']
                total += score(row['match'], 'plant')
                trace = footer(Path(row['trace']))
                traces[(opp, uid)] = (trace['time'], [e for e in trace['activity'] if e['side'] == 'plant'])
        raw[plant] = traces
        strength[plant] = total
    def sequence(item, stop):
        deploys, modes = [], []
        for event in item[1]:
            if event['time'] >= stop:
                continue
            if event['kind'] == 'deploy':
                deploys.append((event['card'], round(event['time'], 1)))
            elif event['kind'] == 'plan' and (not modes or modes[-1][1] != event['mode']):
                modes.append((round(event['time'], 1), event['mode']))
        return deploys, modes
    for a, b in itertools.combinations(strength, 2):
        samples = []
        for key, left in raw[a].items():
            right = raw[b][key]
            stop = min(300., left[0], right[0])
            ld, lm = sequence(left, stop)
            rd, rm = sequence(right, stop)
            if ld != rd or lm != rm:
                samples.append(dict(opponent=key[0], opening=key[1], deployments_different=ld != rd, modes_different=lm != rm,
                    first_different_deployment=next(([x,y] for x,y in itertools.zip_longest(ld,rd) if x!=y),None)))
        pairs[''.join(sorted([a,b]))] = samples
    # Require a winning aggregate and maximize the least pairwise behavioral difference.
    def rank(group):
        d = [len(pairs[''.join(sorted(ab))]) for ab in itertools.combinations(group,2)]
        return (min(d),sum(d),sum(strength[k] for k in group))
    eligible=[k for k in strength if strength[k]>=15]
    selected = max(itertools.combinations(eligible,3), key=rank)
    assert rank(selected)[0] > 0
    write(OUT/'opponents.json',dict(strength=strength, comparisons=pairs, selected=selected,
          model_sha256={k:sha(MODELS[k]) for k in strength}, screening_games_per_policy=36,
          definition='Plant deploy card/time or attack/defend switches differ before min(300s, both durations). Strength gate at least +15 in 36.'))


def prepare():
    inputs_ok()
    assert sha(BASE)==read(PRIOR_HOME/'snapshot-only/frozen.json')['model_sha256']
    marker=OUT/'prepared.json'
    if marker.exists():
        frozen=read(marker)
        assert frozen['index']==sha(OUT/'plain/index.json') and frozen['opponents']==sha(OUT/'opponents.json')
        return
    same_opening_screen()
    cmd(EXPORT/'deck73_corpus.exe',OUT/'draft.json',6,3,971000,192831)
    scenarios=[s for s in read(OUT/'draft.json') if s['map']=='家院']
    assert len(scenarios)==36 and all(not s.get('error') and not s.get('invalid') for s in scenarios)
    old_seeds=set()
    for path in [PREV/'scenarios.json', PRIOR_HOME/'scenarios.json', NIGHT/'scenarios.json']:
        if path.exists():old_seeds.update(x.get('seed') for x in read(path))
    assert not old_seeds.intersection(s['seed'] for s in scenarios)
    ordered=sorted(scenarios,key=lambda x:(x['seed']//1000,x['night'],x['seed']))
    # Six openings per deck-generation batch, both light states. Separate batches for split.
    groups=[ordered[:12],ordered[12:18],ordered[18:]]
    assert all(len({s['seed'] for s in g})==len(g) and sum(s['night'] for s in g)==len(g)//2 for g in groups)
    write(OUT/'scenarios.json',ordered)
    write(OUT/'plan.json',dict(train=[f'{i:03}' for i in range(12)],validation=[f'{i:03}' for i in range(12,18)],
         test=[f'{i:03}' for i in range(18,36)],seeds=[s['seed'] for s in ordered],release_sha256=read(NIGHT/'plan.json')['release_sha256'],
         protocol='Select three behaviorally distinct strong plants from earlier home data. Optimize the zombie position head by paired native returns; freeze zombie before optimizing plant economic readout. Select using training/validation only. Fresh test: parent and candidates vs r22 and historical strong heads; extend every new loss-to-timeout to 1200 seconds and check prefix.'))
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',OUT/'plain')
    write(OUT/'prepared.json',dict(index=sha(OUT/'plain/index.json'),opponents=sha(OUT/'opponents.json')))


def guarded(stage):
    OUT.mkdir(exist_ok=True)
    scratch=OUT/'temp'
    scratch.mkdir(exist_ok=True)
    path=OUT/'disk.json'
    disks=[PREV,NIGHT,BUILD,PRIOR_HOME]
    prior=sum(size(directory) for directory in disks)
    peak=read(path)['peak'] if path.exists() else 0
    def check():
        nonlocal peak
        used=size(OUT)
        free=shutil.disk_usage(OUT).free
        peak=max(used,peak)
        write(path,dict(current=used,peak=peak,prior=prior,free=free,cap=LIMIT,reserve=RESERVE,free_floor=FREE_FLOOR))
        if used+prior>LIMIT-RESERVE or free<FREE_FLOOR or (OUT/'STOP').exists():
            raise RuntimeError('Disk or stop guard')
    check()
    with (OUT/(stage+'.log')).open('ab') as log:
        proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',stage],cwd=R,
             env=dict(os.environ,PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',TMP=str(scratch),TEMP=str(scratch)),
             stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        try:
            while proc.poll() is None:
                check()
                time.sleep(2)
            check()
            if proc.returncode:raise RuntimeError(f'See {stage}.log')
        except BaseException:
            kill_owned(proc)
            raise

if __name__=='__main__':
    if sys.argv[1]=='worker':
        if sys.argv[2]=='prepare':prepare()
        elif sys.argv[2]=='build':
            from position_build import build
            build()
        elif sys.argv[2]=='history':
            from position_history import run
            run()
        elif sys.argv[2]=='fork':
            from position_counterfactual import run
            run()
            from position_hintcheck import run as check_hints
            check_hints()
        elif sys.argv[2]=='robust':
            from position_robust import run
            run()
        elif sys.argv[2]=='horizons':
            from position_horizons import run
            run()
        else:
            from position_train import run
            run()
    else:guarded(sys.argv[1])

