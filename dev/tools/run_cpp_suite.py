"""Run every collected native test module in isolated processes; fail closed on missing results."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_test_waivers import DEFAULT_POLICY, evaluate_module, load_waivers
from native_test_scheduling import run_modules
from native_regression_report import combat_errors, fire_errors, report_failures
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
                ("native","extract/data/catalog.json"),("native","extract/data/__init__.json"),
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

def make_scratch_dir(out, scratch_root):
    if scratch_root is None:
        if os.name == "nt":
            local_appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        else:
            local_appdata = Path(tempfile.gettempdir())
        scratch_root = local_appdata / "PVZNativeTestScratch"
    scratch_root = scratch_root.resolve()
    if scratch_root == out or out in scratch_root.parents:
        raise ValueError("Fixture scratch must be outside the test results directory: " + str(scratch_root))
    scratch_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="suite-", dir=str(scratch_root)))


def build_fixture(out, reference, root):
    """Mirror the original layout in scratch and record the read-only inputs in the report."""
    import shutil,stat
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


def resume_modules(plan_file, out, grouped, source_hashes, waivers):
    """Reuse accepted module reports after a reviewed, bounded input change."""
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    plan = read(plan_file)
    previous = (plan_file.parent / plan["previous_run"]).resolve()
    rerun = set(plan["rerun_modules"])
    if previous == out or not plan["reason"].strip() or rerun - grouped.keys():
        raise ValueError("Invalid resumption plan")
    for name in ("input-versions.json", "collection.json", "bytecode-ref-fingerprints.json", "waiver-policy.json"):
        if file_sha(previous / name) != file_sha(out / name):
            raise ValueError("Cannot resume with different " + name)
    old_sources = read(previous / "source-hashes.json")
    changed_sources = {name for name in old_sources.keys() | source_hashes.keys()
                       if old_sources.get(name) != source_hashes.get(name)}
    old_fixture = read(previous / "fixture-manifest.json")["files"]
    new_fixture = read(out / "fixture-manifest.json")["files"]
    changed_fixture = {name for name in old_fixture.keys() | new_fixture.keys()
                       if old_fixture.get(name) != new_fixture.get(name)}
    if changed_sources != set(plan["changed_sources"]) or changed_fixture != set(plan["changed_fixtures"]):
        raise ValueError("Inputs differ from the reviewed resumption plan: "
                         + repr(sorted(changed_sources)) + " / " + repr(sorted(changed_fixture)))

    reused = {}
    for module in sorted(grouped.keys() - rerun):
        status_file = previous / (module + ".status.json")
        report_file = previous / (module + ".json")
        if not status_file.is_file() or not report_file.is_file():
            continue
        status, results = read(status_file), read(report_file)
        verdict = evaluate_module(module, grouped[module], results, status["exit"],
                                  status["hero_guard_violations"], status["report_error"], waivers)
        if not verdict["accepted"] or any(status.get(key) != value for key, value in verdict.items()):
            continue
        for suffix in (".json", ".status.json", ".log", ".hero-guard.jsonl"):
            source = previous / (module + suffix)
            if source.is_file():
                shutil.copy2(str(source), str(out / source.name))
        reused[module] = status
    evidence = dict(plan, previous_run=str(previous), previous_source_manifest_sha256=file_sha(previous / "source-hashes.json"),
                    reused_reports={module: file_sha(out / (module + ".json")) for module in reused})
    (out / "resume-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return reused


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);ap.add_argument("--workers",type=worker_count,default=None,help="auto (default) or a positive maximum; memory admission still applies");ap.add_argument("--worker-memory-mib",type=positive_int,default=1536);ap.add_argument("--memory-reserve-mib",type=positive_int,default=1024);ap.add_argument("--timeout",type=int,default=600);ap.add_argument("--module",action="append");ap.add_argument("--reference",default=str(REFERENCE));ap.add_argument("--exe",default=None,help="cpp_tests.exe to run (default cpp_tests.exe beside --app-run)");ap.add_argument("--strict",action="store_true",help="Disable the user-approved temporary exact-failure waivers");ap.add_argument("--app-run",default=str(ROOT/"build/app-typed72-v2/Release/app_run.exe"),help="app_run.exe for the PvP73 pure-typed dynamic-path gate")
    ap.add_argument("--baseline", type=Path, help="Complete previous full-suite summary (defaults to latest release)")
    ap.add_argument("--resume-plan", type=Path, help="Reviewed JSON plan to reuse accepted reports from a prior interrupted run")
    ap.add_argument("--scratch-root", type=Path, help="Parent for per-run fixtures and worker temp files; use an unindexed directory (Windows default: %%LOCALAPPDATA%%/PVZNativeTestScratch)")
    args=ap.parse_args()
    if args.resume_plan and args.module:
        ap.error("--resume-plan applies to a full collection")
    # Both the frozen async-function ASTs and bytecode capture policy were
    # produced by CPython 3.8. sys.executable also runs the relay fixtures.
    # Refuse an incompatible interpreter before copying fixtures or testing.
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3,8):
        fixture_python=Path(args.reference)/"modkit/tools/python38-embed/python.exe"
        raise RuntimeError("Frozen native fixtures require CPython 3.8; run this script with "+str(fixture_python))
    policy_hash=file_sha(DEFAULT_POLICY) if DEFAULT_POLICY.exists() else None
    waivers={} if args.strict else load_waivers()
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise RuntimeError("Refusing to reuse nonempty test results: "+str(out))
    scratch = make_scratch_dir(out, args.scratch_root)
    fixture_root = scratch / "fixture-root"
    out.mkdir(parents=True,exist_ok=True)
    # Keep the scratch paths available for subsequent inspection and bytecode controls.
    (out/"scratch-paths.json").write_text(json.dumps({
        "run_scratch": str(scratch), "fixture_root": str(fixture_root),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if policy_hash:(out/"waiver-policy.json").write_bytes(DEFAULT_POLICY.read_bytes())
    build_fixture(out, Path(args.reference), fixture_root)
    fingerprints=bytecode_ref_fingerprints(out,Path(args.reference),fixture_root)
    exe=Path(args.exe).resolve() if args.exe else Path(args.app_run).resolve().with_name("cpp_tests.exe")
    version_inputs={"build":json.loads((ROOT/"extract/data/__init__.json").read_text(encoding="utf-8")),
        "reference":str(Path(args.reference).resolve()),"source_test_origin":"frozen 71 collection; project-owned current assertions in tools/native_test_contracts.py",
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
    baseline=args.baseline
    if baseline is None and not args.module:
        release=json.loads((ROOT/"dist/latest-native-release.json").read_text("utf-8"))
        if release.get("full_regression_report"):baseline=Path(release["full_regression_report"])
    if baseline is not None:
        baseline=baseline.resolve()
        if not baseline.is_file() or baseline.parent==out:raise ValueError("Missing or self-referential baseline: "+str(baseline))
    exe_hash=file_sha(exe)
    build_dir=Path(args.app_run).resolve().parent
    binaries={"cpp_tests":exe,"app_run":Path(args.app_run).resolve(),"audit":build_dir/"pvp744_r4_audit.exe","game":build_dir/"PvZPvPNative.exe"}
    binaries['fire']=build_dir/'fire741_production_audit.exe'
    binary_hashes={name:file_sha(path) for name,path in binaries.items()}
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
    reused = resume_modules(args.resume_plan.resolve(), out, grouped, source_hashes, waivers) if args.resume_plan else {}
    pending = [module for module in selected if module not in reused]
    if args.resume_plan:
        print("RESUME", len(reused), "accepted modules reused;", len(pending), "to run", flush=True)
    started=time.time()
    active={};active_lock=threading.Lock();module_roots={}
    def processes():
        with active_lock:return dict(active)
    def scheduling_event(row):
        with (out/"scheduling.jsonl").open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(row,time=time.time()))+'\n')
        if row['event'] in ('started','waiting_for_memory'):print('SCHEDULER',json.dumps(row),flush=True)
    def run(mod):
        local_fixture=clone_fixture(fixture_root,scratch/"module-fixtures"/mod/"fixture-root") if max_workers>1 else fixture_root
        with active_lock:module_roots[mod]=str(local_fixture)
        worker_temp = scratch / "tmp" / mod
        worker_temp.mkdir(parents=True, exist_ok=True)
        env=os.environ.copy();env.pop("PVZ_TRACE",None)
        env.update(SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy",APPDATA=str(out/"userdata"/mod),PVP_USERDATA=str(out/"userdata"/mod/"pvp_userdata"))
        env.update(PVZ_TEST_ROOT=str(local_fixture), TEMP=str(worker_temp), TMP=str(worker_temp), TMPDIR=str(worker_temp))
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
    statuses,scheduling=run_modules(pending,run,max_workers,args.worker_memory_mib,args.memory_reserve_mib,processes,scheduling_event)
    by_module = {status["module"]: status for status in statuses}
    statuses = [reused[module] if module in reused else by_module[module] for module in selected]
    scheduling['requested_workers']=args.workers or 'auto'
    (out/"module-fixtures.json").write_text(json.dumps(module_roots,ensure_ascii=False,indent=2),encoding='utf-8')
    # Publish unit and animation evidence at the path used by comparison tools.
    if 'test_pvp_native_units' in module_roots:
        for name in ('original-unit-loop-matrix.json','original-native-zombie-real-ticks.json','original-native-zombie-real-ticks.png'):
            rel=Path('对战/测试结果/native-animation')/name
            source=Path(module_roots['test_pvp_native_units'])/rel
            if source.is_file():
                destination = out / "fixture-root" / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
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
    combat_dir = out / "combat-r4"
    combat_dir.mkdir()
    combat_exe = Path(args.app_run).resolve().with_name("pvp744_r4_audit.exe")
    combat = {"passed": False}
    try:
        with (combat_dir / "audit.log").open("wb") as log:
            rc = subprocess.run([str(combat_exe), str(combat_dir)], cwd=str(ROOT),
                                stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout).returncode
        report = json.loads((combat_dir / "results.json").read_text(encoding="utf-8"))
        errors = combat_errors(report)
        combat = {"passed": rc == 0 and not errors, "coverage_errors": errors,
                  "checks": report["checks"], "exit": rc}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        combat["error"] = str(error)
    fire_path=combat_dir/'fire-matrix.json'
    try:
        with (combat_dir/'fire-matrix.log').open('wb') as log:
            env=dict(os.environ,PVP_USERDATA=str(combat_dir/'fire-userdata'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
            rc=subprocess.run([str(binaries['fire']),str(fire_path)],cwd=str(ROOT),env=env,
                              stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout).returncode
        fire=fire_errors(json.loads(fire_path.read_text('utf8')))
        fire_gate=dict(passed=rc==0 and not fire,exit=rc,coverage_errors=fire)
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        fire_gate=dict(passed=False,error=str(error))
    accepted = accepted and combat["passed"] and fire_gate["passed"]
    execution_success = execution_success and combat["passed"] and fire_gate["passed"]
    changed=sorted(set(changed) | {name for name,value in source_hashes.items()
                                  if not (ROOT/name).is_file() or file_sha(ROOT/name)!=value})
    if changed:
        accepted=execution_success=False
    applied=[row for status in statuses for row in status["waived"]]
    waiver_report={"enabled":not args.strict,"policy":str(DEFAULT_POLICY),"policy_sha256":policy_hash,"applied":applied,"unexpected_nonpass":[row for status in statuses for row in status["unexpected_nonpass"]],"resolved":[case for status in statuses for case in status["resolved_waivers"]]}
    (out/"waivers-applied.json").write_text(json.dumps(waiver_report,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"source_changed_during_run":changed,"fixture_changed_during_run":fixture_changed,"exe_changed_during_run":exe_changed,"collection_mismatch":collection_mismatch,"exe":str(exe),"exe_sha256":exe_hash,"seconds":round(time.time()-started,3),"modules":statuses,"counts":{k:sum(s["counts"][k] for s in statuses) for k in ("PASS","FAIL","ERROR","SKIP")},"missing":sum(len(s["missing"]) for s in statuses),"execution_success":execution_success,"success":accepted,"accepted_with_waivers":accepted and bool(applied),"waived":len(applied),"waivers":waiver_report,"scheduling":scheduling,"pure_typed_gate":pure_gate,"combat_r4_gate":combat}
    summary.update(fire_gate=fire_gate,scope="subset" if args.module else "full", collected=len(ids), selected=len(selected),
                   build_version=version_inputs["build"]["BUILD"], binary_sha256=binary_hashes)
    if args.resume_plan:
        summary["resumed"] = {"reused_modules": len(reused), "executed_modules": len(pending),
                              "evidence": str(out / "resume-evidence.json")}
    changed_binaries=[name for name,path in binaries.items() if file_sha(path)!=binary_hashes[name]]
    summary["changed_binaries"]=changed_binaries
    if changed_binaries:summary["success"]=summary["execution_success"]=False
    try:
        triage=report_failures(summary,out,baseline)
    except (ValueError,KeyError,TypeError,OSError) as error:
        triage={"error":str(error)}
        summary["success"]=False
    (out/"failure-triage.json").write_text(json.dumps(triage,ensure_ascii=False,indent=2),encoding="utf-8")
    summary["triage"]={key:value for key,value in triage.items() if key not in ("cases","previous_findings")}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("modules","collection_mismatch")},ensure_ascii=False),flush=True)
    return 0 if summary["success"] else 1
if __name__=="__main__":raise SystemExit(main())
