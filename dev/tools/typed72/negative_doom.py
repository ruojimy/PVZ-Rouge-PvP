"""Independent doom faults: range, live identity, allegiance and list capture."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);original=ROOT/'src/sim/typed/doom_effects.cpp';source=original.read_text(encoding='utf8');digest=sha(original)
    faults=[('range_edge','std::abs(p.x-point.x)<=radius&&std::abs(p.y-point.y)<=radius','std::abs(p.x-point.x)<radius&&std::abs(p.y-point.y)<radius',('doom-range-',)),
        ('live_identity','if(std::find(world_.targets->begin(),world_.targets->end(),target)==world_.targets->end())continue;','/* fault: hit removed retained target */',('doom-live-roster-',)),
        ('allegiance_capture','if(target_charmed==charmed)continue;','if(target_charmed==source->source.charmed.present())continue;',('doom-source-capture-',)),
        ('entity_list_capture','if(entities->size()<=before)return {};','if(world_.runtime.entities.list()->size()<=before)return {};',('doom-visual-hook-',))]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,old,new,prefixes in faults:
        if source.count(old)!=1:raise ValueError('mutation anchor count '+label)
        mutant=out/(label+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8');changes.append(dict(original=str(original),original_sha256=digest,mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64','-DPVZ_TYPED_DOOM_SOURCE='+str(mutant)],
            [a.cmake,'--build',str(build),'--config','Release','--target','doom72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for cmd in commands:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_doom.py'),'--exe',str(build/'Release/doom72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));targeted=[r for r in raw['results'] if any(r['label'].startswith(p) for p in prefixes)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[] if sha(original)==digest else [str(original)];report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
