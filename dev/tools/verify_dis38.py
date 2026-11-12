"""Compare native inspection with this CPython 3.8's dis on real and synthetic wordcode."""
import argparse
import dis
import json
import marshal
import os
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]

def value(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, types.CodeType):
        return {"code": v.co_name}
    if isinstance(v, (tuple, list)):
        return [value(item) for item in v]
    return {"other": True}

def inspect(code, path="root"):
    rows = []
    for ins in dis.get_instructions(code):
        rows.append({field: value(getattr(ins, field)) for field in
                     ("offset", "opcode", "opname", "arg", "argval", "starts_line", "is_jump_target")})
    result = [{"path": path, "instructions": rows}]
    for i, item in enumerate(code.co_consts):
        if isinstance(item, types.CodeType):
            result.extend(inspect(item, path + "/" + str(i)))
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default=r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\reverse_engineered\raw\pvzrouge.pyc")
    args = ap.parse_args()
    if sys.version_info[:2] != (3, 8):
        raise RuntimeError("Run with the reference CPython 3.8")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = marshal.loads(Path(args.source).read_bytes())
    op = dis.opmap
    # Chained EXTENDED_ARG, a wide constant index, forward/absolute jumps, and a no-argument
    # opcode between operands. Jump destinations inside the payload exercise label marking.
    words = [("EXTENDED_ARG", 1), ("EXTENDED_ARG", 0), ("LOAD_CONST", 2),
             ("JUMP_FORWARD", 4), ("NOP", 0), ("NOP", 0), ("JUMP_ABSOLUTE", 8),
             ("LOAD_CONST", 0), ("RETURN_VALUE", 0)]
    payload = bytes(part for name, arg in words for part in (op[name], arg))
    synthetic = root.replace(co_code=payload, co_consts=(None,) + tuple(range(1, 65539)),
                             co_firstlineno=10, co_lnotab=bytes((2, 1, 4, 255, 2, 2)))
    results = []
    env = os.environ.copy()
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", APPDATA=str(out/"appdata"), PVP_USERDATA=str(out/"userdata"))
    for name, code in (("original", root), ("extended-jumps", synthetic)):
        source = out/(name + ".marshal")
        source.write_bytes(marshal.dumps(code))
        target = out/(name + ".native.json")
        with (out/(name + ".log")).open("w", encoding="utf-8") as log:
            run = subprocess.run([str(ROOT/"build/Release/cpp_tests.exe"), "--dis-report", str(source), str(target)],
                                 cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
        if run.returncode:
            raise RuntimeError("Native inspection failed: " + name + " (see log)")
        expected = inspect(code)
        actual = json.loads(target.read_text(encoding="utf-8"))
        (out/(name + ".expected.json")).write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
        if actual != expected:
            for native, python in zip(actual, expected):
                for got, want in zip(native["instructions"], python["instructions"]):
                    if got != want:
                        raise AssertionError((name, native["path"], got, want))
            raise AssertionError((name, "instruction or code-object count differs"))
        results.append(dict(name=name, code_objects=len(actual), instructions=sum(len(c["instructions"]) for c in actual), equal=True))
    (out/"summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results), flush=True)

if __name__ == "__main__":
    main()
