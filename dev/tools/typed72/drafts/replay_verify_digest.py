import argparse,hashlib,json,math,os,random,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    stage=ROOT/'build/typed72-room-stage';old=stage/'v-digest/build/Release/replay_v_digest_probe.exe';new=stage/'build/Release/room_boundary72_probe.exe'
    pinsfile=stage/'v-digest/build-inputs.json';pins=json.loads(pinsfile.read_text(encoding='utf8'));pins[str(pinsfile)]=sha(pinsfile)
    for p in [old,new,Path(__file__).resolve(),stage/'build-inputs.json']:pins[str(p)]=sha(p)
    for p in (stage/'source').rglob('*'):
        if p.is_file():pins[str(p)]=sha(p)
    # Actual successful room outputs exercise deeply nested observed entities,
    # IDs, event lists and all numbers in a mixed native-room composition.
    source=ROOT/'test_results/typed72-20261105/room-work/room-expanded-v3/actual.jsonl';pins[str(source)]=sha(source)
    payloads=[None,True,False,{},[],0,-0.,1.,-1.,1e-6,1e-7,1e16,1e20,1e-300,5e-324,1.7976931348623157e308,9007199254740993,{'z':0,'a':'中文🥔\n\t\b\r\f\u0001\\"','é':'😀','中':'文'}]
    rng=random.Random(720511)
    for i in range(512):
        value=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
        if math.isfinite(value):payloads.append(dict(index=i,value=value,near=[math.nextafter(value,0.) if hasattr(math,'nextafter') else value]))
    for i,line in enumerate(source.read_text(encoding='utf8').splitlines()):
        if i%7==0:
            row=json.loads(line);payloads.append(row[-1] if isinstance(row,list) else row)
    inputs=[dict(kind='digest',payloads=payloads[i:i+32]) for i in range(0,len(payloads),32)]
    data=args.out/'inputs.jsonl';data.write_text('\n'.join(dump(v) for v in inputs)+'\n',encoding='utf8');pins[str(data)]=sha(data);(args.out/'pins.json').write_text(dump(pins),encoding='utf8')
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str((args.out/'userdata').resolve()))
    returns=[]
    for name,exe in [('existing-v',old),('typed',new)]:
        with (args.out/(name+'.log')).open('wb') as log:result=subprocess.run([str(exe),str(data.resolve()),str((args.out/(name+'.jsonl')).resolve())],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        returns.append(result.returncode)
    a=[json.loads(s) for s in (args.out/'existing-v.jsonl').read_text(encoding='utf8').splitlines()];b=[json.loads(s) for s in (args.out/'typed.jsonl').read_text(encoding='utf8').splitlines()]
    failures=[]
    for i in range(max(len(a),len(b))):
        if i>=min(len(a),len(b)):failures.append(dict(batch=i,error='missing output'));continue
        for j in range(max(len(a[i]),len(b[i]))):
            if j>=min(len(a[i]),len(b[i])) or a[i][j]!=b[i][j]:failures.append(dict(index=i*32+j,existing_v=a[i][j] if j<len(a[i]) else None,typed=b[i][j] if j<len(b[i]) else None))
    changed=[p for p,h in pins.items() if sha(Path(p))!=h];summary=dict(passed=not failures and not changed and not any(returns),values=len(payloads),batches=len(inputs),failures=failures,returncodes=returns,changed_inputs=changed,scope='direct retained V json.dumps and pm_catalog::f_digest versus typed canonical serializer and SHA256; includes successful room outputs; no product/replay playback acceptance')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}));return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
