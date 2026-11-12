"""Compare actual native RGBA blits/metadata with the original installed pygame-ce.

No expected pixel values come from the C++ implementation. Includes alpha-zero hidden RGB,
per-pixel and blanket alpha, explicitly disabled blending, opaque targets, and copies/transforms.
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024*1024), b""): h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); args = ap.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", APPDATA=str(out/"python-appdata"), PVP_USERDATA=str(out/"python-userdata"))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(REFERENCE/"modkit"))
    from pvp.app import _pygame
    pg, handles = _pygame(); pg.init(); pg.display.set_mode((1, 1))
    cases, expected = [], []
    colors = [((100,150,200),(20,30,40)), ((0,255,1),(255,0,254)), ((245,17,93),(7,191,250))]
    for (source_rgb,destination_rgb), sa, da, source_alpha, destination_alpha, modulation, transform in itertools.product(
            colors, (0,1,64,128,254,255), (0,1,64,128,255), (False,True), (False,True),
            ("default",None,0,1,64,128,254,255), ("", "copy", "scale", "convert_alpha", "convert")):
        case = dict(source=list(source_rgb)+( [sa] ), destination=list(destination_rgb)+( [da] ),
                    source_alpha=source_alpha, destination_alpha=destination_alpha, transform=transform)
        s = pg.Surface((1,1), pg.SRCALPHA if source_alpha else 0); s.fill(case["source"])
        d = pg.Surface((1,1), pg.SRCALPHA if destination_alpha else 0); d.fill(case["destination"])
        if modulation != "default": case["modulation"] = modulation; s.set_alpha(modulation)
        if transform == "scale": s = pg.transform.scale(s, (1,1))
        elif transform: s = getattr(s, transform)()
        d.blit(s, (0,0))
        expected.append(dict(rgba=list(d.get_at((0,0))), alpha=s.get_alpha(), srcalpha_flag=bool(s.get_flags() & pg.SRCALPHA)))
        cases.append(case)
    version = dict(pygame=pg.version.ver, sdl=list(pg.get_sdl_version()), module=pg.__file__)
    pg.quit(); handles.clear()
    (out/"inputs.json").write_text(json.dumps(cases), encoding="utf-8")
    (out/"python.json").write_text(json.dumps(expected), encoding="utf-8")
    exe = ROOT/"build/Release/cpp_tests.exe"; before = sha(exe)
    source_hashes = {str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"src/pg").glob("*.cpp")}
    env = os.environ.copy(); env.update(APPDATA=str(out/"native-appdata"), PVP_USERDATA=str(out/"native-userdata"))
    with (out/"native.log").open("w", encoding="utf-8") as log:
        process = subprocess.run([str(exe), "--graphics-report", str(out/"inputs.json"), str(out/"native.json")],
                                 cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    if process.returncode: raise RuntimeError("Native graphics report failed; inspect native.log")
    native = json.loads((out/"native.json").read_text(encoding="utf-8"))
    if len(native) != len(expected): raise AssertionError("Missing native graphics results")
    differences = [dict(index=i,input=cases[i],python=a,native=b) for i,(a,b) in enumerate(zip(expected,native)) if a!=b]
    (out/"differences.json").write_text(json.dumps(differences, indent=2), encoding="utf-8")
    changed = [p for p,h in source_hashes.items() if sha(ROOT/p)!=h]
    summary = dict(cases=len(cases), identical=len(cases)-len(differences), differences=len(differences), reference=version,
                   native_exe_sha256=before, exe_unchanged=before==sha(exe), source_changes=changed, source_hashes=source_hashes)
    (out/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="source_hashes"}), flush=True)
    if differences: print(json.dumps(differences[:3]), flush=True)
    return 1 if differences or changed or not summary["exe_unchanged"] else 0

if __name__ == "__main__": raise SystemExit(main())
