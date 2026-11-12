"""Intra-package import graph of modkit/pvp; prints transitive closures."""
import ast, sys
from pathlib import Path
PVP = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvp")
deps = {}
for f in PVP.glob("*.py"):
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except Exception as ex:
        print("PARSE FAIL", f.name, ex); continue
    d = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1:
            if node.module:
                d.add(node.module.split(".")[0])
            else:
                for a in node.names:
                    d.add(a.name)
    deps[f.stem] = {x for x in d if (PVP / (x + ".py")).exists()}


def closure(roots):
    seen = set(); work = list(roots)
    while work:
        m = work.pop()
        if m in seen: continue
        seen.add(m); work += deps.get(m, ())
    return seen

sys.stdout.reconfigure(encoding="utf-8")
size = {f.stem: f.stat().st_size for f in PVP.glob("*.py")}
for roots in sys.argv[1:]:
    c = closure(roots.split(","))
    print("== %s: %d modules, %d KB" % (roots, len(c), sum(size[m] for m in c if "atlas" not in m) // 1024))
    print(" ".join(sorted(c, key=lambda m: -size[m])))
