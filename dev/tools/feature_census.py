import ast, json, sys, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
PVP = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvp")
cov = json.load(open(Path(__file__).resolve().parents[1] / "extract/schema/step_coverage.json", encoding="utf-8"))
files = sorted({k.split(":")[0] for k in cov if k.endswith(".py") or ".py:" in k})
files = [f for f in files if (PVP / f).exists()]
c = collections.Counter()
per = {}
for f in files:
    t = ast.parse((PVP / f).read_text(encoding="utf-8"))
    cc = collections.Counter()
    for n in ast.walk(t):
        k = type(n).__name__
        if k in ("Yield", "YieldFrom", "With", "Try", "Lambda", "ListComp", "DictComp", "SetComp", "GeneratorExp",
                 "ClassDef", "Starred", "JoinedStr", "Nonlocal", "Global", "Set", "Raise", "Assert"):
            cc[k] += 1
        if isinstance(n, ast.Call):
            if n.keywords: cc["kwcall"] += 1
            if isinstance(n.func, ast.Name) and n.func.id in ("getattr", "setattr", "hasattr", "isinstance", "super", "type", "id", "sorted", "enumerate", "zip", "any", "all", "map", "filter", "dict", "set", "frozenset", "next", "iter", "divmod"):
                cc["call:" + n.func.id] += 1
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                cc["deco:" + (d.id if isinstance(d, ast.Name) else d.attr if isinstance(d, ast.Attribute) else "?")] += 1
            if n.args.vararg: cc["*args"] += 1
            if n.args.kwarg: cc["**kw"] += 1
        if isinstance(n, ast.ClassDef) and n.bases:
            cc["base:" + ",".join(ast.unparse(b) if hasattr(ast, "unparse") else (b.id if isinstance(b, ast.Name) else "?") for b in n.bases)] += 1
    per[f] = cc
    c.update(cc)
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    print("%6d %s" % (v, k))
