"""Capture original assertions with one explicit, portable fixture schedule.

Only the unordered head_keys loop in the Python asset-loader fixture is sorted.
The native loader uses the same Unicode key order. No values, pixels or asserted
results are supplied to native code. Full original source/PYC/tool fingerprints,
invocation consumption and state digests remain mandatory. An independent run
of the UNCHANGED original class must have identical pixel observations.
"""
from pathlib import Path
import ast,hashlib,json,sys,argparse,os,collections,importlib
POLICY='native-assets-head-key-order-v1'
ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'tools/bytecode_ref_capture.py').is_file():ROOT=Path(__file__).resolve().parents[2]
def policy_function(source):
    tree=ast.parse(source)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_original_assets')
    loops=[n for n in ast.walk(fn) if isinstance(n,ast.For) and isinstance(n.iter,ast.Name) and n.iter.id=='head_keys']
    if len(loops)!=1:raise RuntimeError('Original head_keys fixture loop shape changed')
    loop=loops[0];loop.iter=ast.copy_location(ast.Call(func=ast.Name(id='sorted',ctx=ast.Load()),args=[loop.iter],keywords=[]),loop.iter)
    return ast.fix_missing_locations(fn)
def capture_policy_metadata(source):
    raw=source.encode('utf-8') if isinstance(source,str) else source
    fn=policy_function(raw.decode('utf-8-sig'))
    return dict(capture_policy_id=POLICY,native_assets_source_sha256=hashlib.sha256(raw).hexdigest(),capture_policy_ast_sha256=hashlib.sha256(ast.dump(fn,include_attributes=False).encode('utf-8')).hexdigest())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--oracle',required=True);a=ap.parse_args()
    O=Path(a.out).resolve();O.mkdir(parents=True,exist_ok=False);sys.dont_write_bytecode=True
    sys.path.insert(0,str(ROOT/'tools'));import bytecode_ref_capture as base
    from run_cpp_suite import build_fixture
    ref=base.TESTS.parent;fixture=build_fixture(O,ref)
    os.environ.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',APPDATA=str(O/'appdata'),PVP_USERDATA=str(O/'userdata'))
    sys.path[:0]=[str(base.TESTS),str(ref/'modkit')]
    source_paths=[ref/'tests/test_pvp_native_animation.py',ref/'reverse_engineered/raw/pvzrouge.pyc']+sorted((ref/'modkit/pvp').glob('*.py'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    before={str(p):sha(p) for p in source_paths}
    import pvp.native_assets as assets
    raw=Path(assets.__file__).read_bytes();fn=policy_function(raw.decode('utf-8-sig'));namespace=dict(vars(assets))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),assets.__file__,'exec'),namespace)
    assets.load_original_assets=namespace['load_original_assets']
    test=importlib.import_module('test_pvp_native_animation');test.ROOT=fixture
    original=test.NativeAnimation.pixels;current=[None];sequence=collections.Counter();pixels=[]
    def observe(self,surface):
        data=original(self,surface);identity=current[0]
        if identity is None:raise RuntimeError('Original pixel observation has no test owner')
        pixels.append(dict(test=identity,sequence=sequence[identity],size=list(surface.get_size()),bytes=len(data),rgba_sha256=hashlib.sha256(data).hexdigest()));sequence[identity]+=1;return data
    test.NativeAnimation.pixels=observe
    import unittest
    old_start=unittest.TextTestResult.startTest;old_stop=unittest.TextTestResult.stopTest
    def start(self,case):current[0]=case.id();return old_start(self,case)
    def stop(self,case):result=old_stop(self,case);current[0]=None;return result
    unittest.TextTestResult.startTest=start;unittest.TextTestResult.stopTest=stop
    output=O/'test_pvp_native_animation.json'
    sys.argv=[base.__file__,'test_pvp_native_animation',str(output)];base.main()
    doc=json.loads(output.read_text('utf-8'));doc['baseline_capture_tool_sha256']=sha(Path(base.__file__));doc['tool_sha256']=sha(Path(__file__))
    doc.update(capture_policy_metadata(raw));doc['capture_fixture_scope']='Only unordered head_keys iteration is sorted; original tests/assertions and all observed original function values/pixels unchanged.'
    output.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (O/'pixels.json').write_text(json.dumps(pixels,ensure_ascii=False,indent=2),encoding='utf-8')
    oracle=json.loads(Path(a.oracle).read_text('utf-8'))
    left={(x['test'],x['sequence']):x for x in oracle};right={(x['test'],x['sequence']):x for x in pixels}
    differences=[dict(key=k,original=left.get(k),stable_fixture=right.get(k)) for k in sorted(set(left)|set(right)) if left.get(k)!=right.get(k)]
    (O/'pixel-differences.json').write_text(json.dumps(differences,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(scope=doc['capture_fixture_scope'],policy=capture_policy_metadata(raw),original_assertions=doc['python_outcome'],original_pixels=len(oracle),stable_fixture_pixels=len(pixels),pixel_differences=len(differences),sources_before=before,sources_unchanged=before=={str(p):sha(p) for p in source_paths},invocations={k:len(v) for k,v in doc['cases'].items()},tool_sha256=doc['tool_sha256'],baseline_capture_tool_sha256=doc['baseline_capture_tool_sha256'])
    (O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in summary.items() if k!='sources_before'},ensure_ascii=False))
    return int(bool(differences) or not summary['sources_unchanged'] or bool(doc['python_outcome']['failures']) or bool(doc['python_outcome']['errors']) or doc['python_outcome']['run']!=10)
if __name__=='__main__':raise SystemExit(main())
