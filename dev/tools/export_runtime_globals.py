"""Export unpatched NativeRuntime tables, preserving container and dictionary-key types.

NativeBattle owns its later mutations. Feeding a completed battle's tables back into
NativeRuntime applies some edits twice and leaks presentation globals into the raw world.
"""
import hashlib
import json
import marshal
import os
from pathlib import Path
import sys

TOOL = Path(__file__).resolve()
ROOT = TOOL.parents[1]
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.dont_write_bytecode = True
sys.path[:0] = [str(REF/"tests"), str(REF/"modkit")]
os.chdir(str(REF))
import multiworker_fixtures as fixtures
from pvp.maps import build_snapshot
from pvp.native_runtime import NativeRuntime

def encode(value):
    if value is None or type(value) in (bool, int, float, str): return value
    if type(value) is list: return [encode(item) for item in value]
    if type(value) is tuple: return {"@tuple": [encode(item) for item in value]}
    if type(value) in (set, frozenset): return {"@set": [encode(item) for item in sorted(value, key=repr)]}
    if type(value) is dict: return {"@dict": [[encode(key), encode(item)] for key, item in value.items()]}
    raise TypeError(type(value).__name__)

source = REF/"reverse_engineered/raw/pvzrouge.pyc"
root = marshal.loads(source.read_bytes())
bridge = fixtures.bridge()
worlds = [NativeRuntime(root, build_snapshot(bridge, name, seed).to_dict(), seed=seed) for name, seed in (("家院", 1), ("大桥", 7))]
static, dynamic, skipped = {}, [], []
for key in sorted(set(worlds[0].g) | set(worlds[1].g)):
    if key == "__builtins__": skipped.append(key); continue
    try: first, second = (encode(world.g.get(key)) for world in worlds)
    except TypeError: skipped.append(key); continue
    if first == second: static[key] = first
    else: dynamic.append(key)
target = ROOT/"extract/data/_runtime_static.json"
target.write_text(json.dumps(static, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
manifest = dict(pyc_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                native_runtime_sha256=hashlib.sha256((REF/"modkit/pvp/native_runtime.py").read_bytes()).hexdigest(),
                tool_sha256=hashlib.sha256(TOOL.read_bytes()).hexdigest(),
                output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), static=len(static), dynamic=dynamic, skipped=skipped)
(ROOT/"extract/schema/runtime-static-provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(static=len(static), dynamic=len(dynamic), skipped=len(skipped), output=str(target))), flush=True)
