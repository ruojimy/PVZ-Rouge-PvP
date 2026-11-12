# Translate old-suite test modules (next-pvp71/tests/test_pvp_*.py) to C++ and register their test cases.
#   python38 tools/gen_cpp_tests.py <module> [module ...]      (or @file with one module per line)
# Output: src/cpptests/gen/pm_*.{h,cpp} (pvp2cpp, unchanged test code) + src/cpptests/registry.cpp
# Test collection follows unittest's loader: every TestCase subclass bound in the module namespace (own classes
# and `from x import Cls`), every test* method including inherited ones, in sorted name order.
import ast, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\tests")
GEN = ROOT / "src" / "cpptests" / "gen"
PY = sys.executable
DUAL = ["content_assets", "expansion_assets", "pvp64_sprite_atlas", "pvp67_assets", "pvp66_icons"]

def parse(mod):
    return ast.parse((TESTS / (mod + ".py")).read_text(encoding="utf-8"))

def test_imports(tree):
    """alias -> test module for `import test_pvp_x as y` and `from test_pvp_x import C`"""
    mods, names = {}, {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("test_pvp_"):
                    mods[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and n.module.startswith("test_pvp_"):
            for a in n.names:
                names[a.asname or a.name] = (n.module, a.name)
    return mods, names

CACHE = {}
REFERENCE_COLLECTION = {}
def info(mod):
    if mod not in CACHE:
        tree = parse(mod)
        mods, names = test_imports(tree)
        classes = {}
        aliases = {}
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                methods = [f.name for f in n.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
                classes[n.name] = dict(bases=n.bases, methods=methods)
            elif isinstance(n, ast.Assign) and isinstance(n.value, (ast.Name, ast.Attribute)):
                for target in n.targets:
                    if isinstance(target, ast.Name): aliases[target.id] = n.value
        CACHE[mod] = dict(tree=tree, mods=mods, names=names, classes=classes, aliases=aliases)
    return CACHE[mod]

def resolve(mod, base):
    """-> ('testcase',) | (module, class) | None"""
    I = info(mod)
    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
        if base.value.id == "unittest" and base.attr in ("TestCase", "IsolatedAsyncioTestCase"):
            return ("testcase",)
        if base.value.id in I["mods"]:
            return resolve(I["mods"][base.value.id], ast.Name(id=base.attr, ctx=ast.Load()))
    if isinstance(base, ast.Name):
        if base.id in I["classes"]:
            return (mod, base.id)
        if base.id in I["names"]:
            m, name = I["names"][base.id]
            if name in info(m)["classes"]: return (m, name)
            return resolve(m, ast.Name(id=name, ctx=ast.Load()))
        if base.id in I["aliases"]:
            return resolve(mod, I["aliases"][base.id])
        if base.id == "TestCase":
            return ("testcase",)
    return None

def mro(mod, cls, seen=None):
    """C3-ish linearization sufficient for single/simple multiple inheritance: (module, class) list."""
    seen = set() if seen is None else seen
    if (mod, cls) in seen: return []
    seen.add((mod, cls))
    out = [(mod, cls)]
    for b in info(mod)["classes"][cls]["bases"]:
        r = resolve(mod, b)
        if r and r != ("testcase",):
            for x in mro(*r, seen=seen):
                if x not in out:
                    out.append(x)
    return out

def is_testcase(mod, cls):
    for m, c in mro(mod, cls):
        for b in info(m)["classes"][c]["bases"]:
            if resolve(m, b) == ("testcase",):
                return True
    return False

def collect(mod):
    if mod in REFERENCE_COLLECTION:
        record = REFERENCE_COLLECTION[mod]
        if record.get("loader_errors"):
            raise RuntimeError("Original unittest collection failed for " + mod)
        return record["bindings"]
    I = info(mod)
    bound = {c: (mod, c) for c in I["classes"]}
    bound.update({k: v for k, v in I["names"].items() if v[1] in info(v[0])["classes"]})
    cases = []
    for name, (m, c) in sorted(bound.items()):
        if not is_testcase(m, c):
            continue
        tests = []
        for mm, cc in mro(m, c):
            for meth in info(mm)["classes"][cc]["methods"]:
                if meth.startswith("test") and meth not in tests:
                    tests.append(meth)
        if tests:
            cases.append(dict(binding=name, module=m, cls=c, tests=sorted(tests)))
    return cases

def deps(mods):
    out, todo = [], list(mods)
    while todo:
        m = todo.pop()
        if m in out:
            continue
        out.append(m)
        I = info(m)
        todo += list(I["mods"].values()) + [v[0] for v in I["names"].values()]
    return out

def ident(n):
    return re.sub(r"\W", "_", n)

def main():
    global REFERENCE_COLLECTION
    args = sys.argv[1:]
    registry_only = "--registry-only" in args
    if registry_only:
        args.remove("--registry-only")
    if "--reference-collection" in args:
        index = args.index("--reference-collection")
        path = Path(args[index + 1])
        REFERENCE_COLLECTION = json.loads(path.read_text(encoding="utf-8"))
        del args[index:index + 2]
    if args and args[0].startswith("@"):
        args = [l.strip() for l in open(args[0][1:], encoding="utf-8") if l.strip() and not l.startswith("#")]
    targets = args
    allmods = deps(targets)
    GEN.mkdir(parents=True, exist_ok=True)
    stage = ROOT / "build/cpp-test-generation/cpptests/gen"
    stage.mkdir(parents=True, exist_ok=True)
    if not registry_only:
        r = subprocess.run([PY, str(ROOT / "tools" / "pvp2cpp.py"), str(stage), "pvzunit"] + allmods,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("\n".join(l for l in r.stdout.splitlines() if "todo=0" not in l))
        if r.returncode:
            print(r.stderr[-3000:])
            raise SystemExit(r.returncode)
    # UI dual modules: the game's UI links pm_ui_<m> (tools/ui_dual.py)
    pat = re.compile(r"\b(pm|init_deps)_(%s)\b" % "|".join(DUAL))
    for module in ([] if registry_only else ["pvzunit"] + allmods):
        for ext in (".cpp", ".h"):
            f = stage / ("pm_" + module + ext)
            t = f.read_text(encoding="utf-8")
            n = pat.sub(lambda m: "%s_ui_%s" % (m.group(1), m.group(2)), t)
            dest = GEN / f.name
            if not dest.exists() or dest.read_text(encoding="utf-8") != n:
                dest.write_text(n, encoding="utf-8")
    # registry of every generated test module present in GEN (batches accumulate)
    present = sorted(p.stem[3:] for p in GEN.glob("pm_test_pvp_*.h"))
    # Missing production modules block a module and every translated dependent.
    # Record them explicitly; never replace the missing API by a successful stub.
    blocked, uses = {}, {}
    for mod in ["pvzunit"] + present:
        uses[mod] = set()
        for ext in (".cpp", ".h"):
            text = (GEN / ("pm_" + mod + ext)).read_text(encoding="utf-8")
            for path in re.findall(r'^#include "([^"]+)"', text, re.M):
                if not (ROOT / "src" / path).exists():
                    blocked[mod] = "missing production/test dependency: " + path
                if path.startswith("cpptests/gen/pm_"):
                    uses[mod].add(Path(path).stem[3:])
    changed = True
    while changed:
        changed = False
        for mod, imports in uses.items():
            if mod not in blocked and any(d in blocked for d in imports):
                blocked[mod] = "blocked dependency: " + next(d for d in imports if d in blocked)
                changed = True
    (GEN.parent / "collection-blocked.json").write_text(json.dumps(blocked,ensure_ascii=False,indent=2),encoding="utf-8")
    cm = ["set(PVZ_CPPTEST_GENERATED_SRC"]
    cm += ['  "${CMAKE_SOURCE_DIR}/src/cpptests/gen/pm_%s.cpp"' % m for m in ["pvzunit", "baseline61_art_fixture"] + present if m not in blocked]
    cm.append(")")
    (GEN.parent / "sources.cmake").write_text("\n".join(cm)+"\n",encoding="utf-8")
    print("COMPILE_BLOCKED",json.dumps(blocked,ensure_ascii=False))
    entries, inc = [], set()
    total = {}
    for mod in present:
        if mod in blocked: continue
        for case in collect(mod):
            inc.add(mod); inc.add(case["module"])
            entries.append((mod, case))
            total[mod] = total.get(mod, 0) + len(case["tests"])
    L = ["// Generated by tools/gen_cpp_tests.py - do not edit by hand.", '#include "cpptests/registry.h"']
    L += ['#include "cpptests/gen/pm_%s.h"' % m for m in sorted(inc)]
    L.append("namespace pvz::cpptests {")
    L.append("const std::vector<Case>& registry() {")
    L.append("    static const std::vector<Case> cases = {")
    for mod, c in entries:
        L.append('        {"%s", "%s", "%s", [] { pm_%s::init(); return pm_%s::cls_%s(); }, {%s}},' % (
            mod, c["binding"], c["cls"], c["module"], c["module"], ident(c["cls"]),
            ", ".join('"%s"' % t for t in c["tests"])))
    L.append("    };")
    L.append("    return cases;")
    L.append("}")
    L.append("}  // namespace pvz::cpptests")
    registry = ROOT / "src/cpptests/registry.cpp"
    content = "\n".join(L) + "\n"
    if not registry.exists() or registry.read_text(encoding="utf-8") != content:
        registry.write_text(content,encoding="utf-8")
    identities = {}
    for mod in present:
        identities[mod] = [dict(binding=c["binding"], test=t,
                                canonical_id=c["module"] + "." + c["cls"] + "." + t)
                           for c in collect(mod) for t in c["tests"]]
    (GEN.parent / "test-identities.json").write_text(json.dumps(identities, indent=2), encoding="utf-8")
    summary = json.load(open(Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\对战\测试结果\pvp71-suite-groups\summary.json"), encoding="utf-8"))
    old = {m["module"]: m["tests"] for m in summary["modules"]}
    for m in targets:
        print("%-40s collected %3d   old suite ran %s" % (m, total.get(m, 0), old.get(m, "?")))

if __name__ == "__main__":
    main()
