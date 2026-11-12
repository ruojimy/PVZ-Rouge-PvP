"""Exercise reference fingerprint/sequence gates and native-result corruption in separate processes.

Only isolated negative-control fixtures are changed. Original tests and captures remain read-only.
"""
import argparse
import copy
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODULE = "test_pvp_native_physics"
PREFIX = MODULE + ".NativePhysicsTests."
FAST = "test_original_tail_and_balloon_effects_match_every_native_tick"
NATIVE = "test_original_water_and_ladder_full_block_matches_every_tick"

def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def audit(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixture-run", required=True)
    args = ap.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    fixture = Path(args.fixture_run).resolve()
    ref_dir = ROOT/"references/bytecode"
    original = ref_dir/(MODULE + ".json")
    inputs = [original, ROOT/"tools/bytecode_ref_capture.py", fixture/"bytecode-ref-fingerprints.json"]
    before = {str(path): sha(path) for path in inputs}
    fingerprints = json.loads((fixture/"bytecode-ref-fingerprints.json").read_text(encoding="utf-8"))
    doc = json.loads(original.read_text(encoding="utf-8"))
    calls = doc["cases"][PREFIX + FAST]
    doc["cases"] = {PREFIX + FAST: calls}
    gc.collect()
    results = []

    def run(name, test=FAST, changes=None, fingerprint=None, reference=ref_dir):
        folder = out/name; folder.mkdir()
        fp = folder/"fingerprints.json"
        fp.write_text(json.dumps(fingerprint or fingerprints), encoding="utf-8")
        env = os.environ.copy()
        for key in ("PVZ_BYTECODE_REF_TAMPER", "PVZ_NEGATIVE_CONTROL_NATIVE"):
            env.pop(key, None)
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", APPDATA=str(folder/"appdata"),
                   PVP_USERDATA=str(folder/"userdata"), PVZ_TEST_ROOT=str(fixture/"fixture-root"),
                   PVZ_BYTECODE_REF_DIR=str(reference), PVZ_BYTECODE_REF_FINGERPRINTS=str(fp),
                   PVZ_BYTECODE_REF_AUDIT=str(folder/"audit.jsonl"))
        env.update(changes or {})
        with (folder/"run.log").open("w", encoding="utf-8") as log:
            process = subprocess.run([str(ROOT/"build/Release/cpp_tests.exe"), "-m", MODULE, "-k", test,
                                      "--json", str(folder/"results.json")], cwd=str(ROOT), env=env,
                                     stdout=log, stderr=subprocess.STDOUT, timeout=1500)
        rows = json.loads((folder/"results.json").read_text(encoding="utf-8"))
        if len(rows) != 1 or rows[0]["test"] != test:
            raise AssertionError((name, "wrong execution identity", rows))
        result = dict(name=name, exit=process.returncode, outcome=rows[0]["outcome"], detail=rows[0]["detail"])
        results.append(result); print(json.dumps(result), flush=True)
        return result

    def rejected(name, marker=None, **kwargs):
        result = run(name, **kwargs)
        if result["exit"] == 0 or result["outcome"] not in ("FAIL", "ERROR") or (marker and marker not in result["detail"]):
            raise AssertionError((name, "negative control was not rejected as expected", result))

    if run("baseline-fast")["outcome"] != "PASS": raise AssertionError("baseline failed")
    for field in ("pyc_sha256", "tool_sha256", "test_source_sha256"):
        altered = copy.deepcopy(fingerprints)
        target = altered["modules"][MODULE] if field == "test_source_sha256" else altered
        target[field] = "0" * 64
        rejected("fingerprint-" + field, marker=field + " does not match", fingerprint=altered)
    rejected("reference-input", marker="native input differs", changes={"PVZ_BYTECODE_REF_TAMPER": "input"})
    rejected("reference-output", changes={"PVZ_BYTECODE_REF_TAMPER": "output"})
    for name, changed in (("unconsumed-call", calls + [calls[-1]]), ("extra-invocation", calls[:-1])):
        refs = out/(name + "-references"); refs.mkdir()
        altered = dict(doc, cases={PREFIX + FAST: changed})
        (refs/(MODULE + ".json")).write_text(json.dumps(altered, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        rejected(name, marker="replayed" if name == "unconsumed-call" else "more reference invocations", reference=refs)
    if run("native-baseline", test=NATIVE)["outcome"] != "PASS": raise AssertionError("native baseline failed")
    corrupted = run("native-corrupted", test=NATIVE, changes={"PVZ_NEGATIVE_CONTROL_NATIVE": "1"})
    if corrupted["outcome"] != "FAIL" or "AssertionError" not in corrupted["detail"]:
        raise AssertionError(("native result corruption must reach the original behavior assertion", corrupted))
    if run("native-recovered", test=NATIVE)["outcome"] != "PASS": raise AssertionError("native recovery failed")
    baseline = audit(out/"native-baseline/audit.jsonl")
    negative = audit(out/"native-corrupted/audit.jsonl")
    recovered = audit(out/"native-recovered/audit.jsonl")
    if not negative or baseline != recovered or negative != baseline[:len(negative)]:
        raise AssertionError("Native corruption changed independent reference inputs/results, or recovery differs")
    after = {str(path): sha(path) for path in inputs}
    if before != after: raise AssertionError("An original input changed")
    summary = dict(success=True, controls=results, original_input_hashes=before,
                   native_corruption_reference_calls_unchanged=len(negative), recovered_reference_calls=len(recovered))
    (out/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "controls"}), flush=True)

if __name__ == "__main__":
    main()
