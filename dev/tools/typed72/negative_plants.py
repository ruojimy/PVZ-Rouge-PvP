"""Build independent plant/terrain/content faults and retain exact failures."""
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
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True)
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    paths={k:ROOT/'src/sim/typed'/v for k,v in dict(PLANT='plant_spawn.cpp',TERRAIN='terrain_effects.cpp',CONTENT='content_target.cpp').items()}
    sources={k:p.read_text(encoding='utf8') for k,p in paths.items()};digests={k:sha(p) for k,p in paths.items()}
    faults=[('pumpkin_priority','PLANT','if(exclude_pumpkin)continue;return i;','if(exclude_pumpkin)continue;',('terrain-destroy-',)),
        ('lottery_rng','PLANT','rt.rng.randint(1,upper)!=1||placement.boss_battle','placement.boss_battle||rt.rng.randint(1,upper)!=1',('lottery-retries-',)),
        ('grave_replacement','TERRAIN','if(auto replaced=world_.terrain.at(cell.y,cell.x))tile=std::move(replaced);','/* fault: retain obsolete tile */',('grave-callback-',)),
        ('charm_presence','CONTENT','!source->charmed.present()','(!source->charmed.present()||source->charmed.is_null())',('content-plant-damage-','content-partial-plant-')),
        ('plant_ellipse','CONTENT','tile*(plant?.45:.5),tile*(plant?.45:.8)','tile*.5,tile*(plant?.5:.8)',('content-contact-',)),
        ('bedrock_guard','PLANT','tile->block.get()=="基岩"','tile->block.get()=="fault:unprotected"',('pvp-bedrock-',))]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,key,old,new,prefixes in faults:
        source=sources[key]
        if source.count(old)!=1:raise ValueError('mutation anchor count '+label)
        mutant=out/(label+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(paths[key]),original_sha256=digests[key],mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        options=['-DPVZ_TYPED_'+k+'_SOURCE='+str(mutant if k==key else p) for k,p in paths.items()]
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64']+options,
            [a.cmake,'--build',str(build),'--config','Release','--target','plants72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for cmd in commands:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_plants.py'),'--exe',str(build/'Release/plants72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));targeted=[r for r in raw['results'] if any(r['label'].startswith(p) for p in prefixes)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(p) for k,p in paths.items() if sha(p)!=digests[k]]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
