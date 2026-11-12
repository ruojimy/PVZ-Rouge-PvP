"""Manual corrections for the few places pydec38 could not structure in the live regions
(each verified against the disassembly; see comments). Run after tools/dump_live_regions.py."""
from pathlib import Path
LIVE = Path(__file__).resolve().parents[1] / "extract" / "live"
FIXES = {
    # entities: the `if shanchu:` impact block ends with JUMP to 108796 = the shared `del 实体[l]`
    "entities.py": [("""                    增粒子(name, [c(实体[l]['位置'][0]), c(实体[l]['位置'][1])], lizi)
            # goto @108796
        continue
    del 实体[l]""", """                    增粒子(name, [c(实体[l]['位置'][0]), c(实体[l]['位置'][1])], lizi)
            del 实体[l]
            continue
        continue
    del 实体[l]""")],
    # plant_maintenance: 116462 / 116898 are the JUMP_ABSOLUTE back-edges of the two `for lzx` loops
    "plant_maintenance.py": [("# goto @116462", "continue"), ("# goto @116898", "continue")],
}
for name, reps in FIXES.items():
    p = LIVE / name
    s = p.read_text(encoding="utf-8")
    for old, new in reps:
        if old not in s:
            if new in s:
                continue
            raise SystemExit("fix_live: pattern not found in %s: %r" % (name, old[:60]))
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
print("fix_live applied")
