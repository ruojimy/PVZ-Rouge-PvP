"""Exact retained-V registration, health and idempotent configuration audit."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools/typed72'),str(Path(__file__).resolve().parent)]
import evidence_archive,evidence_store
from verify_cold_catalog import difference

def cases():
 export=json.loads((ROOT/'test_results/cold-catalog-work/v-export-v1.json').read_text(encoding='utf8'))
 for key,card in export['raw_templates'].items():
  if card['category']=='secret':continue
  plant=card['side']=='plant'
  base={'植物':card['native_input_name'],'植物血':17.,'植物血上限':19.} if plant else {'僵尸':card['native_input_name'],'血量':217.,'防具血量':49.,'移速':31.}
  if card['behavior']=='grave':base.update(_pvp_grave=True,位置=[101.,202.,3.,4.])
  for secrets in ([],['secret:硬化'],['secret:硬化','secret:光疗','secret:地雷']):
   for mode,acting,parent,registered in (
    ('duel',None,None,{}),('duo','plant2',None,{}),('duo','zombie2',{'id':'absent','_pvp_seat':'plant2','_pvp_wave_index':8},{}),
    ('coop','plant2',{'id':'parent','_pvp_seat':'zombie2','_pvp_wave_index':9},{'parent':{'_pvp_seat':'plant','_pvp_wave_index':0}}),
    ('pve',None,{'id':'parent'},{'parent':{'_pvp_wave_index':-1}})):
    native=dict(base)
    if acting=='plant2':native['_pvp_id']='native:21'
    if acting=='zombie2':native['_pvp_id']=''
    yield dict(key=key,side=card['side'],native=native,mode=mode,acting=acting,parent=parent,registered=registered,secrets=secrets,
     ids=12,temporary=mode!='duel',budget_enabled=True,wave=11,actions=(['configure','register','configure','register'] if plant else ['register','register']))
 # Health preserves null/missing HP outside the override set; old IDs and
 # registration order remain stable when the keyed record is replaced.
 for hp in ('missing',None,0.,6.,-3.):
  native={'植物':'模仿者','_pvp_id':'same'}
  if hp!='missing':native['植物血']=hp
  yield dict(key='plant:模仿者',side='plant',native=native,registered={'before':{},'same':{},'after':{}},actions=['register','register'])
 for health in (False,True):
  yield dict(key='zombie:墓碑吞噬者僵尸',side='zombie',native={'僵尸':'墓碑吞噬者僵尸','血量':123.,'_pvp72_health':health},actions=['register','register'])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
 build=a.build.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 built=json.loads((build/'build-report.json').read_text(encoding='utf8'))
 paths=[Path(__file__).resolve(),Path(evidence_archive.__file__).resolve(),Path(evidence_store.__file__).resolve(),build/'build-report.json',Path(__file__).resolve().parent/'verify_cold_catalog.py']
 paths += [build/'build/Release'/(name+'.exe') for name in ('cold_registration_probe','v_cold_registration_probe')]
 pins={str(p):evidence_store.sha256_file(p) for p in paths}
 (out/'pinned.json').write_text(json.dumps(pins,indent=2),encoding='utf8')
 for p in paths:evidence_store.freeze_file(p,out/'frozen'/p.relative_to(ROOT),expected_sha256=pins[str(p)])
 total=0
 with (out/'inputs.jsonl').open('w',encoding='utf8') as stream:
  for case in cases():stream.write(json.dumps(case,ensure_ascii=False,separators=(',',':'))+'\n');total+=1
 runs={}
 for name,output in (('v_cold_registration_probe','expected.jsonl'),('cold_registration_probe','actual.jsonl')):
  with (out/(name+'.log')).open('wb') as log:runs[name]=subprocess.run([str(build/'build/Release'/(name+'.exe')),str(out/'inputs.jsonl'),str(out/output)],cwd=built['runtime_workdir'],stdout=log,stderr=subprocess.STDOUT,timeout=600)
 failures=[]
 with (out/'inputs.jsonl').open(encoding='utf8') as inputs,(out/'expected.jsonl').open(encoding='utf8') as expected,(out/'actual.jsonl').open(encoding='utf8') as actual:
  for index,line in enumerate(inputs):
   try:found=difference(json.loads(next(expected)),json.loads(next(actual)))
   except Exception as error:found={'error':repr(error)}
   if found:
    failures.append(dict(case=index,difference=found))
    if len(failures)<=40:(out/('failure-%06d.json'%index)).write_text(json.dumps(dict(input=json.loads(line),difference=found),ensure_ascii=False,indent=2),encoding='utf8')
  extra=next(expected,None) is not None or next(actual,None) is not None
 drift=[str(p) for p in paths if evidence_store.sha256_file(p)!=pins[str(p)]]
 source_drift=[p for p,h in built['source'].items() if evidence_store.sha256_file(p)!=h]
 report=dict(passed=not failures and not extra and not drift and not source_drift and all(p.returncode==0 for p in runs.values()),cases=total,passed_cases=total-len(failures),failures=failures,
  process_exit_code=runs['cold_registration_probe'].returncode,reference_exit_code=runs['v_cold_registration_probe'].returncode,changed_inputs=drift,source_drift=source_drift,extra_rows=extra,
  reference='existing-v-hand-NativeBattle-registration',library_provenance=built['library_provenance'],full_product_acceptance=False)
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='failures'}),flush=True)
 return evidence_archive.finish_verification(out,producer=runs['cold_registration_probe'],closed_streams=(actual,expected),behavior_passed=report['passed'])
if __name__=='__main__':sys.exit(main())
