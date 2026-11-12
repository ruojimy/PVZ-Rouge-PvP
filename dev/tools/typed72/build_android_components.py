"""Cross-compile the typed component library/probes; never label them an APK.

Run under the existing Ubuntu WSL environment with its installed Android NDK.
Builds are serial, with separate immutable evidence for each invocation.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ndk',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--abi',choices=['arm64-v8a','x86_64'],required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);ndk=Path(a.ndk).resolve()
    toolchain=ndk/'build/cmake/android.toolchain.cmake'
    if not toolchain.is_file():raise ValueError('installed Android toolchain missing')
    build=ROOT/'build'/('typed72-android-'+a.abi)
    inputs=list((ROOT/'src/sim/typed').glob('*.*'))+list((ROOT/'tools/typed72').glob('*probe.cpp'))
    inputs += [ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'src/core/number_text.h',ROOT/'tools/typed72/zombie_motion_fixture.inc',ROOT/'third_party/nlohmann/json.hpp',Path(__file__).resolve(),ndk/'source.properties']
    pinned={str(p):sha(p) for p in inputs};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    commands=[['cmake','-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Ninja',
        '-DCMAKE_TOOLCHAIN_FILE='+str(toolchain),'-DANDROID_ABI='+a.abi,'-DANDROID_PLATFORM=android-23','-DANDROID_STL=c++_static','-DCMAKE_BUILD_TYPE=Release'],
        ['cmake','--build',str(build),'--parallel','1']]
    results=[]
    for n,command in enumerate(commands):
        with (out/('command-%d.log'%n)).open('wb') as log:
            run=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        results.append(dict(command=command,exit_code=run.returncode,log=str(out/('command-%d.log'%n))))
        if run.returncode:break
    names=['typed','hero','protection','targets','patch','spawn','entity','projectiles','plants','doom','chili','sourced','death','registry','aim','wind','lantern','service','fume','squash','pea','shooting']
    names.extend(['world_rules','resources','seat_paths','maintenance','plant_region','plant_utilities','grave_binding','plant_aim','content_queries','september_plants','flying_plants','reed_plants','mortar_plants','scarecrow','scripted_spawn','grenadiers','content_zombies64','native_summons'])
    files=[build/'libpvztyped72.a']+[build/(name+'72_probe') for name in names]
    artifacts={str(p):dict(sha256=sha(p),bytes=p.stat().st_size) for p in files if p.is_file()}
    drift=[str(p) for p in inputs if sha(p)!=pinned[str(p)]]
    report=dict(passed=len(results)==2 and all(r['exit_code']==0 for r in results) and len(artifacts)==len(files) and not drift,
        abi=a.abi,android_api=23,commands=results,artifacts=artifacts,input_drift=drift,
        component_cross_build_only=True,device_execution=False,APK_built=False,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],abi=a.abi,artifacts=len(artifacts),device_execution=False,APK_built=False)))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
