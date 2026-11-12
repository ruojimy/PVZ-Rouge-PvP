"""Run every integrated probe through its existing reference verifier.

Verifiers stay unchanged; each only receives the integrated --exe.  A probe
without a known verifier is reported as unverified rather than skipped.

    python run_integrated_regression.py --probes build/typed72-integrated-v3-probes3 --out test_results/typed72-20261106/integrated-v3 [--only a,b] [--jobs 3]
"""
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/'tools/typed72';DRAFTS=TOOLS/'drafts'
SPECIAL={'hero':'verify_heroes','entity':'verify_entities','service':'verify_services','pea':'verify_peas','maintenance':'verify_plant_maintenance',
    'fume':'verify_fume','plants':'verify_plants','wind':'verify_wind','lantern':'verify_lantern','aim':'verify_aim','targets':'verify_targets',
    'patch':'verify_patch','chili':'verify_chili','doom':'verify_doom','death':'verify_death','sourced':'verify_sourced','spawn':'verify_spawn',
    'projectiles':'verify_projectiles','protection':'verify_protection','registry':'verify_registry','squash':'verify_squash','shooting':'verify_shooting',
    'world_rules':'verify_world_rules','content_zombies64':'verify_content_zombies64','room':'verify_room','room_match':'room_verify_match',
    'room_public':'room_verify_public','room_boundary':'room_verify_boundary','room_transport':'room_verify_transport',
    'replay_lifecycle':'replay_verify_lifecycle','replay_journal':'replay_verify_journal','ai_firing':'ai_verify_firing',
    'ai_observation':'ai_verify_observation','ai_plant_placement':'ai_verify_plant_placement','ai_tactical':'ai_verify_tactical','bonus':'verify_bonus'}
# Verifiers defined against the live drafts (not tools) because their probe only lives there.
PREFER_DRAFT={'content_controllers','content_zombies','content_queries','native_clock','native_tick','native_status','native_summons','bonus',
    'expansion_garden','expansion_combat','room','cold_registration'}
PHASE=ROOT/'build/typed72-phase50-unified-v1/verify_phase50_integrated.py'
def verifier(stem):
    if stem=='content_phase':return PHASE if PHASE.exists() else None
    name=SPECIAL.get(stem,'verify_'+stem)+'.py'
    order=(DRAFTS,TOOLS) if stem in PREFER_DRAFT or name.startswith(('room_','ai_','replay_')) else (TOOLS,DRAFTS)
    for folder in order:
        if (folder/name).exists():return folder/name
    return None
def run(job):
    stem,exe,script,out,timeout=job
    start=time.time()
    with (out.parent/(stem+'.console.log')).open('wb') as log:
        env=dict(os.environ,PYTHONIOENCODING='utf-8')
        try:
            rc=subprocess.run([sys.executable,str(script),'--exe',str(exe),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT,cwd=str(ROOT),env=env,timeout=timeout).returncode
        except subprocess.TimeoutExpired:rc='timeout'
    row=dict(probe=stem,verifier=str(script.relative_to(ROOT)),rc=rc,seconds=round(time.time()-start,1))
    summary=out/'summary.json'
    if summary.exists():
        s=json.loads(summary.read_text(encoding='utf8'))
        row.update(passed=s.get('passed'),cases=s.get('cases'),passed_cases=s.get('passed_cases'),steps=s.get('compared_steps',s.get('steps',s.get('states'))),changed_inputs=len(s.get('changed_inputs',[])))
        fails=[r for r in s.get('results',[]) if not r.get('passed')]
        row['failed_labels']=[r.get('label',r.get('case')) for r in fails][:8]
        if fails:row['first_failure']=json.dumps(fails[0].get('first_difference',fails[0].get('difference',fails[0].get('error'))),ensure_ascii=False)[:300]
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probes',required=True);ap.add_argument('--out',required=True);ap.add_argument('--only');ap.add_argument('--jobs',type=int,default=3);ap.add_argument('--timeout',type=int,default=1500);a=ap.parse_args()
    out=(ROOT/a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    only=set(a.only.split(',')) if a.only else None
    jobs=[];rows=[]
    for exe in sorted((ROOT/a.probes/'build/Release').glob('*72_probe.exe')):
        stem=exe.name[:-len('72_probe.exe')]
        if only and stem not in only:continue
        script=verifier(stem)
        if script is None:rows.append(dict(probe=stem,verifier=None,rc=None,passed=None,note='no verifier mapped'));continue
        jobs.append((stem,exe,script,out/stem,a.timeout))
    def flush():
        p=sum(1 for r in rows if r.get('passed') is True)
        (out/'regression.json').write_text(json.dumps(dict(complete=len(rows)>=len(jobs),passed=p,total=len(rows),rows=sorted(rows,key=lambda r:r['probe'])),ensure_ascii=False,indent=1),encoding='utf8')
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        for row in pool.map(run,jobs):
            rows.append(row);flush()
            print(row['probe'],row.get('passed'),row.get('passed_cases'),'/',row.get('cases'),'rc',row['rc'],row['seconds'],row.get('first_failure','')[:160],flush=True)
    flush()
    print('PASS',sum(1 for r in rows if r.get('passed') is True),'of',len(rows))
if __name__=='__main__':main()
