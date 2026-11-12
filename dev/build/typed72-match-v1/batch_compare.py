"""Run compare_match over the same-rule scenario list; one row per scenario."""
import concurrent.futures,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native');STAGE=Path(__file__).resolve().parent
tag=sys.argv[1];jobs=int(sys.argv[2]) if len(sys.argv)>2 else 3
names='empty basic zombie_swarm projectile_storm mixed_late_game hero_inputs grave_economy duo_basic coop_waves'.split()
names+=sorted(p.stem for p in (ROOT/'tools/scenarios').glob('*.json') if p.stem.startswith(('cards_','secrets_')))
if len(sys.argv)>3:names=sys.argv[3].split(',')
OUT=ROOT/'test_results/typed72-20261106'/('batch-'+tag);OUT.mkdir(parents=True,exist_ok=True)
def run(name):
    d=OUT/name
    p=subprocess.run([sys.executable,str(STAGE/'compare_match.py'),name,str(d.relative_to(ROOT))],cwd=str(ROOT),capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'),timeout=3000)
    row=dict(scenario=name,rc=p.returncode)
    c=d/'comparison.json'
    if c.exists():
        s=json.loads(c.read_text(encoding='utf8'));f=s.get('first_difference');g=s.get('field_gaps',{})
        row.update(identical=s.get('identical'),typed_rc=s.get('typed_rc'),ref_lines=s.get('reference_lines'),typed_lines=s.get('typed_lines'),compared=s.get('compared_until_first_difference'),gaps=len(g),gap_sample=list(g)[:4],
            failure=(s.get('typed_report') or {}).get('failure'),unsupported=(s.get('typed_report') or {}).get('unsupported_operations'),
            first=None if not f else dict(t=f['t'],count=f['count'],head=[d0[:4] for d0 in f['differences'][:3]]),stderr=(s.get('typed_stderr') or '')[-300:])
    else:row['error']=p.stderr.decode('utf8','replace')[-400:]
    for key in('reference.jsonl','typed.jsonl','atlas.bin'):
        q=d/key
        if q.exists():q.unlink()
    print(json.dumps(row,ensure_ascii=False)[:520],flush=True);return row
with concurrent.futures.ThreadPoolExecutor(jobs) as pool:rows=list(pool.map(run,names))
identical=[r['scenario'] for r in rows if r.get('identical')]
(OUT/'batch.json').write_text(json.dumps(dict(total=len(rows),identical=len(identical),rows=rows),ensure_ascii=False,indent=1),encoding='utf8')
print('IDENTICAL',len(identical),'of',len(rows),identical)
