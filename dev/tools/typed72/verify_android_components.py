"""Run Android component executables against independently generated oracles.

Only the explicitly selected disposable emulator is accepted. No application
is installed or launched, and no game save path is read or written.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import difference,sha as file_sha
import evidence_archive
from evidence_archive import open_evidence
ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    path=Path(path)
    # Source/build inputs keep their ordinary file hashing contract. Only
    # missing evidence paths are resolved inside the approved archive root.
    return file_sha(path) if path.exists() else evidence_archive.evidence_sha256(path)


def read(p):return json.loads(p.read_text(encoding='utf8'))
def host_path(value):
    if value.startswith('/mnt/c/'):return Path('C:/'+value[7:])
    if value.startswith('/'):return Path('\\\\wsl.localhost\\Ubuntu'+value.replace('/','\\'))
    return Path(value)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('adb','serial','bundle','build-evidence','out'):ap.add_argument('--'+name,required=True)
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    if not re.fullmatch(r'emulator-[0-9]+',a.serial):raise ValueError('this runner requires the explicitly selected emulator')
    adb=[str(Path(a.adb).resolve()),'-s',a.serial]
    def command(args,log=None,timeout=300):
        r=subprocess.run(adb+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        if log:log.write_bytes(r.stdout)
        if r.returncode:raise RuntimeError('adb failed '+repr(args)+': '+r.stdout.decode('utf8',errors='replace')[-2000:])
        return r.stdout.decode('utf8',errors='replace').strip()
    info={k:command(['shell','getprop',k]) for k in ('sys.boot_completed','ro.product.cpu.abi','ro.build.version.sdk','ro.kernel.qemu','ro.build.fingerprint')}
    if info['sys.boot_completed']!='1' or info['ro.kernel.qemu']!='1':raise ValueError('emulator not ready')
    build_folder=Path(a.build_evidence).resolve();build_report=read(build_folder/'summary.json')
    if not build_report['passed'] or build_report['abi']!=info['ro.product.cpu.abi']:raise ValueError('Android ABI/proof mismatch')
    bundle=Path(a.bundle).resolve();bundle_report=read(bundle/'summary.json')
    if not bundle_report['passed']:raise ValueError('reference bundle failed')
    pinned={}
    for path,digest in read(build_folder/'pinned.json').items():
        p=host_path(path)
        if sha(p)!=digest:raise ValueError('Android build input drift '+str(p))
        pinned[str(p)]=digest
    for path,digest in read(bundle/'pinned.json').items():
        if sha(Path(path))!=digest:raise ValueError('reference bundle input drift '+path)
        pinned[path]=digest
    for path,item in build_report['artifacts'].items():
        p=host_path(path)
        if sha(p)!=item['sha256']:raise ValueError('Android artifact drift '+str(p))
        pinned[str(p)]=item['sha256']
    selected={key[8:]:item for key,item in bundle_report['results'].items() if key.startswith('release-')}
    for item in selected.values():
        evidence=Path(item['evidence']);r=read(evidence)
        if not r['passed'] or sha(evidence)!=item['sha256']:raise ValueError('invalid reference '+str(evidence))
        for path,digest in read(evidence.parent/'pinned.json').items():
            if sha(Path(path))!=digest:raise ValueError('reference input drift '+path)
        for name in ('summary.json','inputs.jsonl','expected.jsonl'):
            p=evidence.parent/name;pinned[str(p)]=sha(p)
    pinned[str(Path(__file__).resolve())]=sha(Path(__file__).resolve())
    for module in (evidence_archive,evidence_archive.store_module):
        p=Path(module.__file__).resolve();pinned[str(p)]=sha(p)
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    (out/'device.json').write_text(json.dumps(info,indent=2),encoding='utf8')
    remote='/data/local/tmp/pvp72-'+out.name
    if not re.fullmatch(r'/data/local/tmp/pvp72-[A-Za-z0-9_-]+',remote):raise ValueError('unsafe temporary name')
    check=subprocess.run(adb+['shell','test','-e',remote],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check.returncode==0:raise ValueError('emulator evidence path already exists')
    command(['shell','mkdir',remote],out/'mkdir.log')
    reports={}
    for name,item in selected.items():
        folder=out/name;folder.mkdir();reference=Path(item['evidence']).parent
        prefix={'stages':'typed','heroes':'hero','entities':'entity','services':'service','peas':'pea',
                'entity_phase':'world_rules','zombie_motion':'world_rules','zombie_actions':'world_rules',
                'hero_physics':'world_rules','hero_phase':'world_rules','bite_boundaries':'world_rules',
                'path_tracking':'resources','hero_recovery':'resources','economy':'resources',
                'grave_clock':'maintenance','plant_maintenance':'maintenance'}.get(name,name)
        filename=prefix+'72_probe'
        candidates=[host_path(path) for path in build_report['artifacts'] if path.endswith('/'+filename)]
        if len(candidates)!=1:raise ValueError('missing Android probe '+filename)
        binary=remote+'/'+filename;inputs=remote+'/'+name+'-inputs.jsonl';output=remote+'/'+name+'-actual.jsonl'
        try:
            command(['push',str(candidates[0]),binary],folder/'push-binary.log');command(['shell','chmod','700',binary])
            command(['push',str(reference/'inputs.jsonl'),inputs],folder/'push-input.log')
            args=['shell',binary,inputs]+([] if name=='stages' else [output])
            with (folder/('actual.jsonl' if name=='stages' else 'stdout.log')).open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
                run=subprocess.run(adb+args,stdout=stdout,stderr=stderr,timeout=600)
            if name!='stages':command(['pull',output,str(folder/'actual.jsonl')],folder/'pull.log')
            results=[];labels=read(reference/'summary.json')['results']
            with open_evidence(reference/'expected.jsonl',encoding='utf8') as expected,(folder/'actual.jsonl').open(encoding='utf8') as actual:
                for i,text in enumerate(expected):
                    row=dict(case=i,label=labels[i].get('label',labels[i].get('mode')),passed=False)
                    try:
                        want=json.loads(text);got=json.loads(next(actual))
                        if name=='stages':
                            if got.get('backend_actual')!='typed72-stages' or got.get('fallback_count')!=0:raise ValueError('unexpected backend or fallback')
                            got={k:got[k] for k in want}
                        diff=difference(want,got);row.update(passed=diff is None,first_difference=diff)
                    except Exception as exc:row['error']=repr(exc)
                    results.append(row)
                    if not row['passed']:(folder/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
                extra=next(actual,None)
            result=dict(passed=run.returncode==0 and all(r['passed'] for r in results) and len(results)==item['cases'] and extra is None,
                cases=len(results),passed_cases=sum(r['passed'] for r in results),steps=item['steps'],process_exit_code=run.returncode,results=results,
                executable_sha256=sha(candidates[0]),reference=str(reference/'summary.json'),actual_sha256=sha(folder/'actual.jsonl'))
        except Exception as exc:result=dict(passed=False,error=repr(exc))
        (folder/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        reports[name]={k:v for k,v in result.items() if k!='results'};reports[name]['evidence']=str(folder/'summary.json')
        print(name,json.dumps(reports[name]),flush=True)
    invariants=json.loads(command(['shell',remote+'/typed72_probe','--self-test'],out/'invariants.json'))
    capabilities=json.loads(command(['shell',remote+'/typed72_probe','--capabilities'],out/'capabilities.json'))
    drift=[path for path,digest in pinned.items() if sha(Path(path))!=digest]
    report=dict(passed=all(r['passed'] for r in reports.values()) and len(reports)==len(selected) and not drift and capabilities.get('full_battle_supported') is False,
        results=reports,input_drift=drift,device=info,state_invariants=invariants,emulator_only=True,physical_device_tested=False,
        bundle=str(bundle/'summary.json'),android_build=str(build_folder/'summary.json'),full_product_acceptance=False,APK_tested=False,formal_performance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],runs=len(reports),emulator_only=True,full_product_acceptance=False)))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
