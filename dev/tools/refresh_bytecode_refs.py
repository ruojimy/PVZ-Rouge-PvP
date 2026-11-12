"""Re-capture with the unchanged collector in an isolated, source-identical test layout.

Only the collector's TESTS/PYC locations are configured in memory. Its code, canonicalization,
fingerprints, original test bytes and reference implementation remain unchanged. Test outputs
and userdata stay inside the new evidence directory; earlier captures are retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.path.insert(0, str(ROOT/"tools"))
sys.dont_write_bytecode = True
from run_cpp_suite import build_fixture, file_sha

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--module", action="append", required=True)
    ap.add_argument("--worker", action="store_true"); ap.add_argument("--fixture")
    args = ap.parse_args(); out = Path(args.out).resolve()
    if args.worker:
        import bytecode_ref_capture as collector
        fixture = Path(args.fixture).resolve()
        collector.TESTS = fixture/"tests"; collector.PYC = fixture/"reverse_engineered/raw/pvzrouge.pyc"
        # The cloned test layout has no interpreter/runtime payload. Load the same read-only
        # reference pygame binaries explicitly, while all test output paths remain isolated.
        runtime = REFERENCE/"modkit/tools/pvp-runtime"
        sys.path.insert(0, str(runtime)); runtime_handles = []
        if hasattr(os, "add_dll_directory"):
            runtime_handles.extend(os.add_dll_directory(str(p)) for p in (runtime, runtime/"pygame"))
            import ctypes
            for name in ("zlib1.dll", "libpng16-16.dll", "libjpeg-62.dll", "libwebp-7.dll"):
                if (runtime/name).is_file(): runtime_handles.append(ctypes.WinDLL(str(runtime/name)))
        sys.path.insert(0, str(REFERENCE/"modkit")); os.chdir(str(fixture))
        sys.argv = [str(ROOT/"tools/bytecode_ref_capture.py"), args.module[0], str(out)]
        collector.main(); return 0
    out.mkdir(parents=True, exist_ok=False)
    fixture = build_fixture(out, REFERENCE)
    manifest = {}
    for source in sorted((REFERENCE/"tests").glob("*.py")):
        target = fixture/"tests"/source.name; shutil.copy2(str(source), str(target)); os.chmod(str(target), stat.S_IREAD)
        original_sha, copied_sha = file_sha(source), file_sha(target)
        if original_sha != copied_sha: raise AssertionError("Test copy changed: " + source.name)
        manifest[source.name] = original_sha
    (out/"test-source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    previous = out/"previous"; previous.mkdir()
    records = []
    collector = ROOT/"tools/bytecode_ref_capture.py"; collector_sha = file_sha(collector)
    for module in args.module:
        target = ROOT/"references/bytecode"/(module + ".json")
        if target.exists(): shutil.copy2(str(target), str(previous/target.name))
        captured = out/(module + ".json")
        env = os.environ.copy(); env.update(PYTHONDONTWRITEBYTECODE="1", SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
            APPDATA=str(out/"userdata"/module/"appdata"), PVP_USERDATA=str(out/"userdata"/module/"pvp_userdata"))
        with (out/(module + ".log")).open("w", encoding="utf-8") as log:
            process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--out", str(captured),
                "--fixture", str(fixture), "--module", module], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1500)
        if process.returncode: raise RuntimeError("Reference capture failed: " + module)
        doc = json.loads(captured.read_text(encoding="utf-8"))
        if doc["python_outcome"]["failures"] or doc["python_outcome"]["errors"]: raise AssertionError((module, doc["python_outcome"]))
        if doc["tool_sha256"] != collector_sha or doc["test_source_sha256"] != manifest[module+".py"] or doc["pyc_sha256"] != file_sha(REFERENCE/"reverse_engineered/raw/pvzrouge.pyc"):
            raise AssertionError("Collector provenance mismatch: " + module)
        staging = target.with_suffix(".json.new-capture")
        shutil.copyfile(str(captured), str(staging)); os.replace(str(staging), str(target))
        records.append(dict(module=module, python_tests=doc["python_outcome"]["run"], captured_cases=len(doc["cases"]),
                            invocations=sum(len(calls) for calls in doc["cases"].values()), sha256=file_sha(target)))
        print(json.dumps(records[-1]), flush=True)
    if file_sha(collector) != collector_sha: raise AssertionError("Collector source changed")
    (out/"summary.json").write_text(json.dumps(dict(collector_sha256=collector_sha, wrapper_sha256=file_sha(Path(__file__).resolve()),
        original_test_root=str(REFERENCE/"tests"), execution_fixture_root=str(fixture), records=records), indent=2), encoding="utf-8")
    return 0

if __name__ == "__main__": raise SystemExit(main())
