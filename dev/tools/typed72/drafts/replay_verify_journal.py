import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp/audit_log.py'
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cases():
    out=[]
    for i in range(24):
        ops=[dict(op='append',event=dict(tick=j,side='plant',payload=dict(type='move',move=j%3-1,label='植物🧟'+str(j)))) for j in range(17+i)]
        ops.insert(5,dict(op='visit_append',event=dict(tick=9000,message='iteration extent')))
        ops.insert(7,dict(op='export',metadata=dict(format='fixture',build='first')))
        ops.append(dict(op='export',metadata={}));ops.append(dict(op='export',metadata=dict(format='fixture',build='replacement')))
        if i%3==0:ops.extend([dict(op='append',event=dict(too_large='x'*5000)),dict(op='append',event={'after':'failure'})])
        if i%3==1:ops.extend([dict(op='corrupt',text='2\n{}\n'),dict(op='inspect')])
        ops.extend([dict(op='close'),dict(op='append',event={})]);out.append(dict(entries=3+i%4,bytes=200+i%7*70,record=1024,operations=ops))
    return out
def reference(case,root,AuditLog):
    root.mkdir(parents=True);log=AuditLog(case['entries'],case['bytes'],case['record'],directory=str(root));out=[]
    for op in case['operations']:
        failed=False;extra={}
        try:
            kind=op['op']
            if kind=='append':log.append(op['event'])
            elif kind=='export':
                extra['exported']=dict(op['metadata'],operations=list(log))
                (root/'recording.json').write_text(dump(extra['exported']),encoding='utf8')
            elif kind=='corrupt':(Path(log.storage_path)/'part-00000000.jsonl').write_text(op['text'],encoding='utf8')
            elif kind=='close':
                storage=log.storage_path;log.close();extra['storage_removed']=not storage or not Path(storage).exists()
            elif kind=='visit_append':
                seen=[]
                for row in log:
                    seen.append(row)
                    if len(seen)==1:log.append(op['event'])
                extra['iterated']=seen
        except Exception:failed=True
        rows=[]
        if not log.closed:
            try:
                for row in log:rows.append(row)
            except Exception:failed=True
        out.append(dict(count=len(log),buffered=log.buffered_count,bytes=log.buffered_bytes,spooled=log.spooled_count,closed=log.closed,failed=bool(log.error),operation_failed=failed,events=rows,**extra))
    log.close();return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    stage=ROOT/'build/typed72-room-stage';paths=[a.exe.resolve(),Path(__file__).resolve(),SOURCE,stage/'build-inputs.json'];paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());pins={str(p):sha(p) for p in paths};(a.out/'pins.json').write_text(dump(pins),encoding='utf8')
    spec=importlib.util.spec_from_file_location('actual_audit_reference',SOURCE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);inputs=cases();expected=[reference(c,a.out/'python-storage'/str(i),module.AuditLog) for i,c in enumerate(inputs)]
    for name,values in [('inputs',inputs),('expected',expected)]:(a.out/(name+'.jsonl')).write_text('\n'.join(dump(v) for v in values)+'\n',encoding='utf8')
    with (a.out/'probe.log').open('wb') as log:run=subprocess.run([str(a.exe.resolve()),str((a.out/'inputs.jsonl').resolve()),str((a.out/'actual.jsonl').resolve()),str((a.out/'typed-storage').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=120)
    actual=[json.loads(line) for line in (a.out/'actual.jsonl').read_text(encoding='utf8').splitlines()];failures=[]
    for i,want in enumerate(expected):
        if i>=len(actual) or len(actual[i])!=len(want):failures.append(dict(case=i,error='missing or extra states'));continue
        for j,(x,y) in enumerate(zip(want,actual[i])):
            if x!=y:failures.append(dict(case=i,step=j,expected=x,actual=y));break
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]];summary=dict(cases=len(inputs),pass_cases=len(inputs)-len(failures),states=sum(map(len,expected)),returncode=run.returncode,changed_inputs=changed,failures=failures,scope='actual bounded AuditLog forward iteration, disk segments, sticky error, corrupt partial reads, close cleanup; recording lifecycle is a separate composition test')
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}));return 1 if failures or changed or run.returncode or len(actual)!=len(expected) else 0
if __name__=='__main__':raise SystemExit(main())
