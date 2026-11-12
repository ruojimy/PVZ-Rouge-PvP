"""Compare actual bundled-font metrics and RGBA pixels to the pinned original pygame."""
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
    bundled=Path(pg.__file__).parent/'freesansbold.ttf'
    native=ROOT/'fonts/freesansbold.ttf'
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha(bundled)==sha(native),'Different font asset'
    cases=[dict(font=font,size=size,text=text,aa=aa) for font,size,text,aa in itertools.product(
        (None,'freesansbold.ttf'),(-1,0,1,12,18,24,32,36),('','Ab','左跳'),(False,True))]
    expected=[]
    for case in cases:
        try:
            font=pg.font.Font(case['font'],case['size'])
            image=font.render(case['text'],case['aa'],(231,179,67))
            expected.append(dict(height=font.get_height(),linesize=font.get_linesize(),ascent=font.get_ascent(),descent=font.get_descent(),
                size=list(font.size(case['text'])),image_size=list(image.get_size()),rgba=base64.b64encode(pg.image.tobytes(image,'RGBA')).decode('ascii')))
        except Exception as error:expected.append(dict(error=type(error).__name__))
    version=dict(pygame=pg.version.ver,sdl=list(pg.get_sdl_version()),module=pg.__file__,font_sha256=sha(bundled))
    pg.quit();handles.clear()
    (out/'inputs.json').write_text(json.dumps(cases,ensure_ascii=False),encoding='utf-8')
    (out/'python.json').write_text(json.dumps(expected),encoding='utf-8')
    exe=ROOT/'build/Release/cpp_tests.exe';digest=sha(exe)
    env=os.environ.copy();env['PVP_USERDATA']=str(out/'native-userdata')
    with (out/'native.log').open('w',encoding='utf-8') as log:
        run=subprocess.run([str(exe),'--font-report',str(out/'inputs.json'),str(out/'native.json')],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:raise RuntimeError('Native font report failed')
    actual=json.loads((out/'native.json').read_text(encoding='utf-8'));assert len(actual)==len(expected)
    diff=[dict(index=i,input=cases[i],different_fields=[k for k in set(x)|set(y) if x.get(k)!=y.get(k)]) for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
    (out/'differences.json').write_text(json.dumps(diff,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(cases=len(cases),identical=len(cases)-len(diff),differences=len(diff),reference=version,exe_sha256=digest,exe_unchanged=digest==sha(exe))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    return int(bool(diff) or not summary['exe_unchanged'])
if __name__=='__main__':raise SystemExit(main())
