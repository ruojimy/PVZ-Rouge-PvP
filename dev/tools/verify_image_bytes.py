"""Independent original-pygame pixel/alpha/flag checks for image.frombytes."""
import argparse,base64,hashlib,itertools,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(REFERENCE/'modkit'))
    os.environ.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'reference-userdata'))
    from pvp.app import _pygame
    pg,handles=_pygame();pg.init()
    cases=[]
    for fmt,size,flipped,buffer in itertools.product(('RGB','RGBA','ARGB','BGRA','RGBX'),((1,1),(3,2),(17,9),(0,0),(0,2)),(False,True),('bytes','bytearray')):
        count=size[0]*size[1]*(3 if fmt=='RGB' else 4)
        raw=bytes((index*71+13)%256 for index in range(count))
        cases.append(dict(format=fmt,size=list(size),flipped=flipped,buffer=buffer,base64=base64.b64encode(raw).decode('ascii')))
    for fmt,size,raw,buffer in [('RGBA',(1,1),b'abc','bytes'),('RGBA',(1,1),b'abcde','bytes'),('INVALID',(1,1),b'abcd','bytes'),('RGBA',(-1,1),b'','bytes'),('RGBA',(1,1),b'abcd','str')]:
        cases.append(dict(format=fmt,size=list(size),base64=base64.b64encode(raw).decode('ascii'),buffer=buffer))
    expected=[]
    for c in cases:
        data=base64.b64decode(c['base64'])
        if c['buffer']=='bytearray':data=bytearray(data)
        if c['buffer']=='str':data=data.decode('ascii')
        try:
            image=pg.image.frombytes(data,c['size'],c['format'],c.get('flipped',False))
            expected.append(dict(rgba=base64.b64encode(pg.image.tobytes(image,'RGBA')).decode('ascii'),size=list(image.get_size()),alpha=image.get_alpha(),flags=image.get_flags()&65536))
        except Exception as error:expected.append(dict(error=type(error).__name__))
    version=dict(pygame=pg.version.ver,sdl=list(pg.get_sdl_version()),module=pg.__file__,RLEACCEL=pg.RLEACCEL,RLEACCELOK=pg.RLEACCELOK)
    pg.quit();handles.clear()
    (out/'inputs.json').write_text(json.dumps(cases),encoding='utf-8');(out/'python.json').write_text(json.dumps(expected),encoding='utf-8')
    exe=ROOT/'build/Release/cpp_tests.exe';digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    env=os.environ.copy();env['PVP_USERDATA']=str(out/'native-userdata')
    with (out/'native.log').open('w',encoding='utf-8') as log:
        run=subprocess.run([str(exe),'--image-bytes-report',str(out/'inputs.json'),str(out/'native.json')],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:raise RuntimeError('Native report failed')
    actual=json.loads((out/'native.json').read_text(encoding='utf-8'));assert len(actual)==len(expected)
    differences=[dict(index=i,input=cases[i],python=x,native=y) for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
    (out/'differences.json').write_text(json.dumps(differences,indent=2),encoding='utf-8')
    summary=dict(cases=len(cases),identical=len(cases)-len(differences),differences=len(differences),reference=version,exe_sha256=digest,exe_unchanged=digest==hashlib.sha256(exe.read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    return int(bool(differences) or not summary['exe_unchanged'])
if __name__=='__main__':raise SystemExit(main())
