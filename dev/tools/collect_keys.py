"""Collect every dictionary key used on 僵尸/植物/实体 units and Dave avatars.

Sources: decompiled original + live regions (subscript patterns), the 1.5.0.1
patch source and the PvP package (string literals next to unit-ish variables),
and the runtime schema.  Writes extract/schema/keys.json {coll: {key: type}}.
"""
import re, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.stdout.reconfigure(encoding="utf-8")
keys = {"僵尸": {}, "植物": {}, "实体": {}}
pat = {c: re.compile(re.escape(c) + r"\[[^\[\]]*(?:\[[^\[\]]*\])?[^\[\]]*\]\['([^']+)'\]") for c in keys}
texts = []
for p in list((ROOT / "extract" / "original").rglob("*.py")) + list((ROOT / "extract" / "live").glob("*.py")):
    texts.append(p.read_text(encoding="utf-8"))
for t in texts:
    for c, rx in pat.items():
        for k in rx.findall(t):
            keys[c].setdefault(k, "?")
        # "'K' in 僵尸[x]" / "'K' not in 植物[x]"
        for k in re.findall(r"'([^']+)' (?:not )?in " + re.escape(c) + r"\[", t):
            keys[c].setdefault(k, "?")
# runtime-observed types
schema = json.loads((ROOT / "extract/schema/schema.json").read_text(encoding="utf-8"))
for c in keys:
    for k, types in schema.get(c, {}).items():
        keys[c][k] = "/".join(sorted(types))
# patch source keys: __pvz_sb_K_* constants map to literal key strings
patch = (REF / "modkit/pvzrouge_runtime_patch_source_20260904.py").read_text(encoding="utf-8")
consts = dict(re.findall(r"^(__pvz_sb_K_\w+)\s*=\s*\"([^\"]+)\"", patch, re.M))
out = {c: dict(sorted(v.items())) for c, v in keys.items()}
out["_patch_K_constants"] = consts
avatar = schema.get("avatar", {})
out["avatar"] = {k: "/".join(sorted(v)) for k, v in avatar.items()}
(ROOT / "extract/schema/keys.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for c in ("僵尸", "植物", "实体"):
    print(c, len(out[c]))
print("patch K constants", len(consts))
