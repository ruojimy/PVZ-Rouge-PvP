"""Dependency/source/negative-capability audit for the isolated typed stages.

Fail closed: a passing stage test is never elevated to full-battle acceptance.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();exe=Path(args.exe).resolve();out=Path(args.out)
    out.mkdir(parents=True,exist_ok=False)
    pending=list((ROOT/'src/sim/typed').glob('*.h'))+list((ROOT/'src/sim/typed').glob('*.cpp'))
    seen={};edges=[];errors=[]
    forbidden={'value.h','pyops.h','pyobj.h','pyrt.h','pvprt.h','obj.h','native_closure.h'}
    while pending:
        file=pending.pop().resolve()
        if str(file) in seen:continue
        seen[str(file)]=sha(file)
        if file.name in forbidden:errors.append('Dynamic runtime dependency: '+str(file))
        text=file.read_text(encoding='utf8')
        for inc in re.findall(r'^\s*#include\s*"([^"]+)"',text,re.M):
            candidates=[file.parent/inc,ROOT/'src'/inc]
            target=next((p.resolve() for p in candidates if p.exists()),None)
            if target is None:errors.append('Unresolved local include: '+inc)
            else:edges.append([str(file),str(target)]);pending.append(target)
    # Check actual failure behavior, not just a declared capability flag.
    rejected=[]
    for name,request in [('full-battle',{'mode':'battle'}),('unknown-mode',{'mode':'fallback'}),
        ('unknown-state-field',{'mode':'damage','zombies':[{'_pvp_hero':'zombie'}],'operations':[]})]:
        run=subprocess.run([str(exe)],input=(json.dumps(request)+'\n').encode('utf8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (out/(name+'.stdout')).write_bytes(run.stdout);(out/(name+'.stderr')).write_bytes(run.stderr)
        result=json.loads(run.stderr)
        passed=run.returncode==2 and not run.stdout and result.get('fallback_count')==0
        rejected.append(dict(name=name,passed=passed,exit_code=run.returncode,result=result))
    tests=subprocess.run([str(exe),'--self-test'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    capabilities=json.loads(subprocess.check_output([str(exe),'--capabilities']))
    valid=not errors and all(x['passed'] for x in rejected) and tests.returncode==0 and capabilities.get('full_battle_supported') is False
    report=dict(passed=valid,executable=str(exe),executable_sha256=sha(exe),local_dependencies=seen,
        dependency_edges=edges,errors=errors,negative_capabilities=rejected,
        state_invariants=json.loads(tests.stdout),capabilities=capabilities,formal_typed_product_acceptance=False,
        scope='Local include graph and independently linked typed library; full production call graph not migrated.')
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=valid,dependencies=len(seen),negative_capabilities=len(rejected),formal_typed_product_acceptance=False)))
    return 0 if valid else 1


if __name__=='__main__':raise SystemExit(main())
