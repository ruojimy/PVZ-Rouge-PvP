"""Run every collected native test module in isolated processes; fail closed on missing results."""
import argparse,hashlib,json,os,shutil,subprocess,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_test_waivers import DEFAULT_POLICY, evaluate_module, load_waivers
from native_test_scheduling import run_modules
ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
# Read-only inputs the original tests reach through ROOT=parents[1]. Reference data comes from the original
# workspace (never written: it is copied); game images come from the native build's own shipped copy.
# Production Python sources are deliberately NOT copied: a native test must not pass by reading them.
FIXTURE_COPIES=[("reference","reverse_engineered/raw/pvzrouge.pyc"),
                ("reference","对战/测试结果/pvp61-art/baseline-assets.py"),
                ("reference","tests/test_pvp_66_room_admission_oct16.py"),
                ("reference","tests/test_pvp_spectators49.py"),
                ("reference","tests/test_pvp_network_memory67.py"),
                ("reference","modkit/android/fonts/cjk.ttf"),
                ("reference","modkit/pvzrouge_runtime_patch_source_20260904.py"),
                ("reference","对战/PvP规则数据.json"),("reference","对战/PvP规则与卡池.md"),
                ("reference","server/relay_server.py"),("reference","tests/fixtures"),
                ("reference","tests/legacy_pvp_simulation.py"),
                ("reference","tests/multiworker_fixtures.py"),
                ("reference","tests/fixtures_dart_reference67.py"),
                ("reference","tests/probe_pvp_net_guest_cost.py"),
                ("native","build/Release/图片=>PVZ-Rouge-v1.4.8/图片"),
                ("native","build/Release/音效=>PVZ-Rouge-v1.4.8/音效"),
                ("native","build/Release/音乐=>PVZ-Rouge-v1.4.8/音乐"),
                ("native","extract/data/pvp/assets=>modkit/pvp/assets")]
# The original unit tests save PNGs here before tearDownClass creates it.
FIXTURE_WRITABLE=["tests","对战/测试结果","对战/测试结果/native-animation","对战/实施记录"]

def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda:fh.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()

def build_fixture(out,reference):
    """Create <out>/fixture-root mirroring the original layout; copied files are marked read-only."""
    import shutil,stat
    root=out/"fixture-root"
    if root.exists():raise RuntimeError("Refusing to reuse an existing fixture root: "+str(root))
    manifest={}
    for origin,spec in FIXTURE_COPIES:
        src,_,dst=spec.partition("=>");dst=dst or src
        source=(reference if origin=="reference" else ROOT)/src;target=root/dst
        if not source.exists():raise RuntimeError("Missing fixture input: "+str(source))
        files=[source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for f in files:
            t=target if source.is_file() else target/f.relative_to(source)
            t.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(f),str(t))
            os.chmod(str(t),stat.S_IREAD)
            manifest[str(t.relative_to(root)).replace("\\","/")]={"origin":origin,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
    for d in FIXTURE_WRITABLE:(root/d).mkdir(parents=True,exist_ok=True)
    (out/"fixture-manifest.json").write_text(json.dumps({"reference":str(reference),"files":manifest},ensure_ascii=False,indent=2),encoding="utf-8")
    return root

def bytecode_ref_fingerprints(out,reference,fixture_root):
    """Actual source fingerprints the native replay checks every reference file against (fail closed):
    the pyc the test loads, the ORIGINAL test module source, and the capture tool."""
    sha=file_sha
    actual={"pyc_sha256":sha(fixture_root/"reverse_engineered/raw/pvzrouge.pyc"),
            "tool_sha256":sha(ROOT/"tools/bytecode_ref_capture.py"),"modules":{}}
    for ref in sorted((ROOT/"references"/"bytecode").glob("*.json")):
        src=reference/"tests"/(ref.stem+".py")
        actual["modules"][ref.stem]={"test_source_sha256":sha(src) if src.exists() else None}
        if ref.stem=="test_pvp_native_animation":
            import importlib.util
            spec=importlib.util.spec_from_file_location("_pvz_stable_asset_capture_policy",ROOT/"tools/stable_assets_capture86.py")
            policy_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy_module)
            policy=policy_module.capture_policy_metadata((reference/"modkit/pvp/native_assets.py").read_bytes())
            actual["modules"][ref.stem].update(policy)
            actual["modules"][ref.stem]["tool_sha256"]=sha(ROOT/"tools/stable_assets_capture86.py")

    path=out/"bytecode-ref-fingerprints.json"
    path.write_text(json.dumps(actual,indent=2),encoding="utf-8")
    return path

def positive_int(value):
    parsed=int(value)
    if parsed<1:raise argparse.ArgumentTypeError('Must be a positive integer')
    return parsed

def worker_count(value):
    return None if value=='auto' else positive_int(value)

def clone_fixture(source,target):
    """Private writable directories, shared immutable file bytes via hard links."""
    def link_or_copy(src,dst):
        try:os.link(src,dst)
        except OSError:shutil.copy2(src,dst)
        return dst
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(str(source),str(target),copy_function=link_or_copy)
    return target

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);ap.add_argument("--workers",type=worker_count,default=None,help="auto (default) or a positive maximum; memory admission still applies");ap.add_argument("--worker-memory-mib",type=positive_int,default=1536);ap.add_argument("--memory-reserve-mib",type=positive_int,default=1024);ap.add_argument("--timeout",type=int,default=600);ap.add_argument("--module",action="append");ap.add_argument("--reference",default=str(REFERENCE));ap.add_argument("--exe",default=None,help="cpp_tests.exe to run (default build/Release/cpp_tests.exe)");ap.add_argument("--strict",action="store_true",help="Disable the user-approved temporary exact-failure waivers");ap.add_argument("--app-run",default=str(ROOT/"build/app-typed72-v2/Release/app_run.exe"),help="app_run.exe for the PvP73 pure-typed dynamic-path gate");args=ap.parse_args()
    policy_hash=file_sha(DEFAULT_POLICY) if DEFAULT_POLICY.exists() else None
    waivers={} if args.strict else load_waivers()
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise RuntimeError("Refusing to reuse nonempty test results: "+str(out))
    out.mkdir(parents=True,exist_ok=True)
    if policy_hash:(out/"waiver-policy.json").write_bytes(DEFAULT_POLICY.read_bytes())
    fixture_root=build_fixture(out,Path(args.reference))
    fingerprints=bytecode_ref_fingerprints(out,Path(args.reference),fixture_root)
    # --exe: the cpp_tests binary under test (default: the frozen build/Release one). A new build
    # lives in its own directory; selecting it changes no test, reference or rule.
    exe=Path(args.exe).resolve() if args.exe else ROOT/"build/Release/cpp_tests.exe"
    version_inputs={"build":json.loads((ROOT/"extract/data/__init__.json").read_text(encoding="utf-8")),
        "reference":str(Path(args.reference).resolve()),"source_test_origin":"read-only 71 suite; 72 user-rule conformance is reported separately",
        "ruleset":json.loads((ROOT/"extract/data/catalog.json").read_text(encoding="utf-8")).get("RULES",{}).get("ruleset","pvp71")}
    (out/"input-versions.json").write_text(json.dumps(version_inputs,ensure_ascii=False,indent=2),encoding="utf-8")
    print("INPUT_VERSIONS",json.dumps(version_inputs,ensure_ascii=True),flush=True)
    listing=subprocess.run([str(exe),"--list"],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf-8",errors="replace")
    if listing.returncode:raise RuntimeError("Native collection failed: "+listing.stderr)
    ids=[s.strip() for s in listing.stdout.splitlines() if s.strip()]
    if not ids or len(ids)!=len(set(ids)):raise RuntimeError("Empty or duplicate native collection")
    grouped={}
    for id in ids:grouped.setdefault(id.split(".")[0],[]).append(id)
    selected=args.module or sorted(grouped)
    if len(selected)!=len(set(selected)):raise RuntimeError("Duplicate requested test module")
    if any(m not in grouped for m in selected):raise RuntimeError("Requested module missing from collection")
    max_workers=min(args.workers or (os.cpu_count() or 1),len(selected))
    (out/"collection.json").write_text(json.dumps(grouped,indent=2),encoding="utf-8")
    identities_path=ROOT/"src/cpptests/test-identities.json"
    identities=json.loads(identities_path.read_text(encoding="utf-8")) if identities_path.exists() else {}
    (out/"test-identities.json").write_text(json.dumps(identities,indent=2),encoding="utf-8")
    for snapshot in (ROOT/"src/cpptests/collection-blocked.json",ROOT/"docs/coverage/coverage_map.json"):
        (out/snapshot.name).write_bytes(snapshot.read_bytes())
    collection_mismatch={}
    for mod,tests in identities.items():
        expected={mod+"."+x["binding"]+"."+x["test"] for x in tests}
        actual=set(grouped.get(mod,[]))
        if expected!=actual:
            collection_mismatch[mod]={"missing":sorted(expected-actual),"extra":sorted(actual-expected)}
    (out/"collection-mismatch.json").write_text(json.dumps(collection_mismatch,indent=2),encoding="utf-8")
    exe_hash=file_sha(exe)
    source_files=[p for p in (ROOT/"src").rglob("*") if p.is_file() and p.suffix in (".cpp",".h",".inc",".cmake")]
    source_files+=list((ROOT/"tools").glob("*.py"))+list((ROOT/"tools").glob("*.sh"))+list((ROOT/"android").glob("*.sh"))+[ROOT/"CMakeLists.txt",ROOT/"android/CMakeLists.txt"]
    source_files+=list((ROOT/"tools/pvp72_sources").glob("*.py"))+list((ROOT/"tools/pvp72_sources").glob("*.json"))
    source_files+=list((ROOT/"references/bytecode").glob("*.json"))+list((ROOT/"extract/data").glob("*.json"))+list((ROOT/"extract/schema").glob("*.json"))
    source_files+=list((ROOT/"extract/original").glob("*.py"))+list((ROOT/"docs/coverage").glob("*.json"))
    # The shipped kernel is the integrated stage, not src/sim/typed. Freeze the
    # actual compiled authority and its owning composition drivers as well.
    source_files+=sorted(p for p in (ROOT/"build/typed72-integrated-v44/source/src/sim/typed").rglob("*") if p.is_file() and p.suffix in (".cpp",".h",".inc"))
    source_files+=[ROOT/"build/typed72-match-v1"/n for n in ("match_probe.cpp","frame_layer.inc","snapshot_layer.inc")]
    source_files.append(ROOT/"tools/pvp741_hooks.json")
    source_hashes={str(p.relative_to(ROOT)):file_sha(p) for p in source_files}
    (out/"source-hashes.json").write_text(json.dumps(source_hashes,indent=2),encoding="utf-8")
    started=time.time()
    active={};active_lock=threading.Lock();module_roots={}
    def processes():
        with active_lock:return dict(active)
    def scheduling_event(row):
        with (out/"scheduling.jsonl").open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(row,time=time.time()))+'\n')
        if row['event'] in ('started','waiting_for_memory'):print('SCHEDULER',json.dumps(row),flush=True)
    def run(mod):
        local_fixture=clone_fixture(fixture_root,out/"module-fixtures"/mod/"fixture-root") if max_workers>1 else fixture_root
        with active_lock:module_roots[mod]=str(local_fixture)
        env=os.environ.copy();env.pop("PVZ_TRACE",None)
        env.update(SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy",APPDATA=str(out/"userdata"/mod),PVP_USERDATA=str(out/"userdata"/mod/"pvp_userdata"))
        env.update(PVZ_TEST_ROOT=str(local_fixture))
        # client tests that need a relay run the real Python relay server out of process (tools/relay_fixture_server.py)
        env.update(PVZ_TEST_PYTHON=sys.executable,PVZ_RELAY_FIXTURE=str(ROOT/"tools"/"relay_fixture_server.py"))
        env.update(PVZ_REAL_THREADS="1")   # CPython semantics: test-created threads are real threads
        # independently captured CPython reference runs of original bytecode windows (tools/bytecode_ref_capture.py)
        env.update(PVZ_BYTECODE_REF_DIR=str(ROOT/"references"/"bytecode"),PVZ_BYTECODE_REF_FINGERPRINTS=str(fingerprints))
        env.update(PVP_HERO_GUARD="1",PVP_HERO_GUARD_LOG=str(out/(mod+".hero-guard.jsonl")))
        log=out/(mod+".log");report=out/(mod+".json");t=time.time()
        if report.exists():raise RuntimeError("Refusing to reuse an existing report: "+str(report))
        report_error=None
        try:
            with log.open("w",encoding="utf-8") as fh:
                with subprocess.Popen([str(exe),"-m",mod,"--json",str(report)],cwd=str(ROOT),env=env,stdout=fh,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as proc:
                    with active_lock:active[mod]=proc
                    try:rc=proc.wait(timeout=args.timeout)
                    except subprocess.TimeoutExpired:
                        proc.kill();proc.wait();rc="TIMEOUT"
                    finally:
                        with active_lock:active.pop(mod,None)
        except OSError as error:rc="START_ERROR";report_error=str(error)
        try:results=json.loads(report.read_text(encoding="utf-8"))
        except (OSError,ValueError) as error:results=[];report_error=str(error)
        guard_log=out/(mod+".hero-guard.jsonl")
        guard_violations=len(guard_log.read_text(encoding="utf-8").splitlines()) if guard_log.exists() else 0
        verdict=evaluate_module(mod,grouped[mod],results,rc,guard_violations,report_error,waivers)
        status={"module":mod,"exit":rc,"seconds":round(time.time()-t,3),"expected":len(grouped[mod]),"results":len(results) if isinstance(results,list) else 0,"report_error":report_error,"hero_guard_violations":guard_violations,**verdict}
        print(mod,verdict["counts"],"missing",len(verdict["missing"]),"exit",rc,"waived",len(verdict["waived"]),"accepted",verdict["accepted"],flush=True)
        (out/(mod+".status.json")).write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
        return status
    statuses,scheduling=run_modules(selected,run,max_workers,args.worker_memory_mib,args.memory_reserve_mib,processes,scheduling_event)
    scheduling['requested_workers']=args.workers or 'auto'
    (out/"module-fixtures.json").write_text(json.dumps(module_roots,ensure_ascii=False,indent=2),encoding='utf-8')
    # Preserve the two public unit-report paths used by independent pixel/unit
    # comparison tools. Other writable artifacts remain isolated per module.
    if max_workers>1 and 'test_pvp_native_units' in module_roots:
        for name in ('original-unit-loop-matrix.json','original-native-zombie-real-ticks.json','original-native-zombie-real-ticks.png'):
            rel=Path('对战/测试结果/native-animation')/name
            source=Path(module_roots['test_pvp_native_units'])/rel
            if source.exists():shutil.copy2(str(source),str(fixture_root/rel))
    changed=[name for name,digest in source_hashes.items() if not (ROOT/name).exists() or file_sha(ROOT/name)!=digest]
    fixture_manifest=json.loads((out/"fixture-manifest.json").read_text('utf-8'))['files']
    fixture_changed=[name for name,entry in fixture_manifest.items() if not (fixture_root/name).is_file() or file_sha(fixture_root/name)!=entry['sha256']]
    if policy_hash!=(file_sha(DEFAULT_POLICY) if DEFAULT_POLICY.exists() else None) and str(DEFAULT_POLICY.relative_to(ROOT)) not in changed:changed.append(str(DEFAULT_POLICY.relative_to(ROOT)))
    exe_changed=file_sha(exe)!=exe_hash
    execution_success=not changed and not fixture_changed and not exe_changed and all(s["success"] for s in statuses)
    accepted=not changed and not fixture_changed and not exe_changed and not collection_mismatch and all(s["accepted"] for s in statuses)
    # PvP73: the shipped dynamic battle path must be pure typed C++ (no V boxes/calls inside the typed
    # step / command / AI entries of real app matches). Fail closed: a missing report is a failure.
    gate_dir=out/"pure-typed-gate"
    gate_run=subprocess.run([sys.executable,str(ROOT/"tools/pvp73_pure_typed_gate.py"),"--out",str(gate_dir),"--app-run",args.app_run],cwd=str(ROOT))
    try:pure_gate=json.loads((gate_dir/"pure-typed-gate.json").read_text(encoding="utf-8"))
    except (OSError,ValueError) as error:pure_gate={"passed":False,"error":str(error)}
    pure_gate["exit"]=gate_run.returncode
    accepted=accepted and bool(pure_gate.get("passed")) and gate_run.returncode==0
    execution_success=execution_success and bool(pure_gate.get("passed"))
    applied=[row for status in statuses for row in status["waived"]]
    waiver_report={"enabled":not args.strict,"policy":str(DEFAULT_POLICY),"policy_sha256":policy_hash,"applied":applied,"unexpected_nonpass":[row for status in statuses for row in status["unexpected_nonpass"]],"resolved":[case for status in statuses for case in status["resolved_waivers"]]}
    (out/"waivers-applied.json").write_text(json.dumps(waiver_report,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"source_changed_during_run":changed,"fixture_changed_during_run":fixture_changed,"exe_changed_during_run":exe_changed,"collection_mismatch":collection_mismatch,"exe":str(exe),"exe_sha256":exe_hash,"seconds":round(time.time()-started,3),"modules":statuses,"counts":{k:sum(s["counts"][k] for s in statuses) for k in ("PASS","FAIL","ERROR","SKIP")},"missing":sum(len(s["missing"]) for s in statuses),"execution_success":execution_success,"success":accepted,"accepted_with_waivers":accepted and bool(applied),"waived":len(applied),"waivers":waiver_report,"scheduling":scheduling,"pure_typed_gate":pure_gate}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("modules","collection_mismatch")},ensure_ascii=False),flush=True)
    return 0 if summary["success"] else 1
if __name__=="__main__":raise SystemExit(main())
