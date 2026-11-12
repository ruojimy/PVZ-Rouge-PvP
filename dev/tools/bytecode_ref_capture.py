"""Independent CPython capture of original-bytecode REFERENCE runs for the native old-suite tests.

    python bytecode_ref_capture.py <test module> <out.json> [test-name-substring]

Runs the ORIGINAL, unmodified test module (next-pvp71/tests) in CPython. Only the test module's `exec`
and `types.FunctionType` names are wrapped, to observe every TOP-LEVEL reference invocation the test makes:
  exec(<original code window>, ns)          and   calls of types.FunctionType(<original code>, g)(...)
Nested calls made by the original code itself are executed normally and not recorded separately.

Per invocation (keyed by test id + sequence number) the record holds:
  kind / code_sha256 (sha256 of the executed co_code) / co_name
  input_digest   digest of the canonical state before the call (globals + args)
  changes        canonical value of every top-level state entry that changed (data entries only)
  removed        data entries that disappeared
  after_digest   digest of the full canonical state afterwards (verifies aliasing after replay)
  result         canonical return value (function calls), exception type/message if it raised
  rng            whether any random state (module or Random object in the state) was consumed
The C++ side (src/cpptests/bytecode_ref.cpp) executes the REAL native product for the system under test and
replays only these reference invocations, refusing any whose input digest differs (fail closed).

CANONICAL FORM (identical in bytecode_ref.cpp; it only changes representation):
  None / bool                     -> null / true / false
  int, float                      -> ["n", "%.17g" % float(x)]   (the native runtime has one number type;
                                     assertEqual treats 1 == 1.0 too, so no assertion meaning is lost)
  str -> ["s", text]   bytes -> ["b", hex]   bytearray -> ["ba", hex] (mutable: identity tracked)
  list -> ["L", [...]]   tuple -> ["T", [...]]   set/frozenset -> ["S", sorted]
  dict and types.SimpleNamespace -> ["D", [[key_text, value]...]] sorted by key_text (the native SimpleNamespace
                                     is a dict; native unit records do not keep insertion order, so key ORDER
                                     is not compared - keys and values are)
  a dict entry "get_pressed" holding a callable -> ["P", [held[1], held[2], held[3]]] (the key state the
                                     original windows read: 左走=1 右走=2 跳跃=3), evaluated on both sides
  repeated mutable container (list / dict / set / bytearray / namespace) -> ["@", first-visit index]
                                     (aliasing is part of the state; traversal order is deterministic)
  functions, lambdas, builtins, classes -> ["f"]   modules -> ["m"]   other objects -> ["o", type name]
  the object the state's pygame.key.get_pressed() returns, wherever stored -> ["K"] (object identity; the
                                     native held-keys dict and python's _HeldKeys have the same 1/2/3 membership)
  top-level key "__builtins__" is ignored (exec inserts it).
CHANGES (replay data, not digests): each changed data entry is encoded with the rules above, except that a
  container also reachable from ANOTHER entry (an unchanged one, or a changed one earlier in sorted order) is
  written as ["@p", [entry, step...]] so the replay binds the SAME native object (aliasing preserved);
  "rebound" lists entries CPython re-bound to another object (the replay rebinds instead of merging in place).
  After applying, the native full-state digest must equal after_digest (values AND aliasing), else error.
NOT COMPARABLE, by rule: addresses / id() values are never recorded (identity is expressed only as aliasing);
  ["o", type] objects cannot be replayed (error); random state consumed by the reference -> replay refuses.
State digest: sha256 of a length-prefixed serialisation of the canonical form (see ser()).
"""
import builtins, hashlib, importlib, json, os, random, sys, types, unittest
from pathlib import Path

TESTS = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\tests")
PYC = TESTS.parent / "reverse_engineered/raw/pvzrouge.pyc"


def num(x):
    return "%.17g" % float(x)


MUTABLE = (list, dict, set, frozenset, bytearray, types.SimpleNamespace)


class Canon:
    """pressed: the object the state's pygame.key.get_pressed() returns -> ["K"] wherever it is stored.
    external: id -> path of containers whose shortest path lies in ANOTHER state entry -> ["@p", path]
    (used only when encoding a change, so a replay re-binds the existing object instead of copying it)."""
    def __init__(self, pressed=None, external=None):
        self.memo, self.pressed, self.external = {}, pressed, external or {}

    def key(self, k):
        return json.dumps(Canon().val(k), ensure_ascii=False, separators=(",", ":"))

    def val(self, v):
        if v is None or isinstance(v, bool):
            return v
        if self.pressed is not None and v is self.pressed:
            return ["K"]
        if isinstance(v, MUTABLE) and id(v) in self.external:
            return ["@p", self.external[id(v)]]
        if isinstance(v, (int, float)):
            return ["n", num(v)]
        if isinstance(v, str):
            return ["s", v]
        if isinstance(v, bytes):
            return ["b", v.hex()]
        if isinstance(v, tuple):
            return ["T", [self.val(x) for x in v]]
        if isinstance(v, (list, dict, set, frozenset, bytearray, types.SimpleNamespace)):
            if id(v) in self.memo:
                return ["@", self.memo[id(v)]]
            self.memo[id(v)] = len(self.memo)
            if isinstance(v, bytearray):
                return ["ba", bytes(v).hex()]
            if isinstance(v, list):
                return ["L", [self.val(x) for x in v]]
            if isinstance(v, (set, frozenset)):
                return ["S", sorted((self.val(x) for x in v), key=lambda c: json.dumps(c, ensure_ascii=False))]
            d = vars(v) if isinstance(v, types.SimpleNamespace) else v
            rows = []
            for k in sorted(d, key=self.key):
                x = d[k]
                if k == "get_pressed" and callable(x):
                    held = x()
                    rows.append([self.key(k), ["P", [bool(held[1]), bool(held[2]), bool(held[3])]]])
                else:
                    rows.append([self.key(k), self.val(x)])
            return ["D", rows]
        if isinstance(v, types.ModuleType):
            return ["m"]
        if callable(v):
            return ["f"]
        return ["o", type(v).__name__]


def ser(c):
    """Length-prefixed serialisation (no JSON escaping questions on either side)."""
    if c is None:
        return "N"
    if c is True:
        return "T"
    if c is False:
        return "F"
    if isinstance(c, int):   # alias index of ["@", n]
        return "i%d" % c
    if isinstance(c, str):
        b = c.encode("utf-8")
        return "s%d:%s" % (len(b), c)
    return "[" + ",".join(ser(x) for x in c) + "]"


def is_data(c):
    return not (isinstance(c, list) and c and c[0] in ("f", "m"))


def state_items(g, args, kwargs):
    items = [("g:" + Canon().key(k), v) for k, v in g.items() if k != "__builtins__"]
    items += [("a:%d" % i, v) for i, v in enumerate(args)]
    items += [("k:" + k, v) for k, v in (kwargs or {}).items()]
    return sorted(items, key=lambda kv: kv[0])


def pressed_of(g):
    """The key-state object of the state's pygame.key.get_pressed (the reference stores it in a global)."""
    try:
        pg = g.get("pygame") if isinstance(g, dict) else None
        key = pg.get("key") if isinstance(pg, dict) else getattr(pg, "key", None)
        fn = key.get("get_pressed") if isinstance(key, dict) else getattr(key, "get_pressed", None)
        if callable(fn) and not isinstance(fn, types.ModuleType):
            return fn()
    except Exception:
        pass
    return None


def container_paths(items):
    """For every mutable container: the shortest paths from up to TWO different state entries (multi-source BFS;
    ties by sorted entry / key order). A path is [entry, step...]; a step is a list index or a dict key text.
    Encoding a change of entry k then references any container that is also reachable from another entry."""
    from collections import deque
    paths, queue = {}, deque((v, [k]) for k, v in items)
    while queue:
        v, p = queue.popleft()
        if not isinstance(v, MUTABLE):
            continue
        seen = paths.setdefault(id(v), [])
        if len(seen) >= 2 or any(q[0] == p[0] for q in seen):
            continue
        seen.append(p)
        if isinstance(v, list):
            queue.extend((x, p + [i]) for i, x in enumerate(v))
        elif isinstance(v, (dict, types.SimpleNamespace)):
            d = vars(v) if isinstance(v, types.SimpleNamespace) else v
            c = Canon()
            for k in sorted(d, key=c.key):
                queue.append((d[k], p + [c.key(k)]))
    return paths


def snapshot(g, args, kwargs):
    items = state_items(g, args, kwargs)
    pressed = pressed_of(g)
    c = Canon(pressed)
    full = [[k, c.val(v)] for k, v in items]
    per = {k: Canon(pressed).val(v) for k, v in items}
    digest = hashlib.sha256(ser(full).encode("utf-8")).hexdigest()
    return digest, per, items, pressed


def encode_changes(changed, items, pressed):
    paths = container_paths(items)
    values = dict(items)
    out = {}
    for k in changed:
        external = {}
        for i, ps in paths.items():
            # an unchanged entry, or a changed entry earlier in order (no reference cycles between changes)
            other = next((p for p in ps if p[0] != k and (p[0] not in changed or p[0] < k)), None)
            if other is not None:
                external[i] = other
        out[k] = Canon(pressed, external).val(values[k])
    return out


def rng_states(g):
    out = [random.getstate()]
    for v in g.values():
        if isinstance(v, random.Random):
            out.append(v.getstate())
    return out


class Recorder:
    def __init__(self):
        self.cases, self.current, self.depth = {}, None, 0
        self.real_exec = builtins.exec

    def invoke(self, kind, code, g, args, kwargs, run):
        if self.depth or self.current is None:
            return run()
        before_digest, before, before_items, _ = snapshot(g, args, kwargs)
        before_ids = {k: id(v) for k, v in before_items}
        rng_before = rng_states(g)
        rec = dict(kind=kind, code_sha256=hashlib.sha256(code.co_code).hexdigest(), co_name=code.co_name,
                   input_digest=before_digest,
                   # per-entry digests: only for diagnosing WHICH entry differs when a native input is refused
                   input_keys={k: hashlib.sha256(ser(v).encode("utf-8")).hexdigest()[:16] for k, v in before.items()})
        self.depth += 1
        try:
            result = run()
            exc = None
        except Exception as e:  # recorded, then re-raised exactly
            result, exc = None, e
        finally:
            self.depth -= 1
        after_digest, after, after_items, pressed = snapshot(g, args, kwargs)
        dump = os.environ.get("PVZ_BYTECODE_REF_DUMP_AT")   # "<test id>#<seq>=<file>": diagnostics only
        if dump and dump.split("=")[0] == "%s#%d" % (self.current, len(self.cases.get(self.current, []))):
            c = Canon(pressed)
            Path(dump.split("=", 1)[1]).write_text(json.dumps([[k, c.val(v)] for k, v in after_items], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        changed = [k for k, v in after.items() if is_data(v) and before.get(k) != v]
        rec["changes"] = encode_changes(changed, after_items, pressed)
        # entries the reference RE-BOUND to another object (vs. mutated in place): a replay must rebind them too
        after_ids = {k: id(v) for k, v in after_items}
        rec["rebound"] = sorted(k for k in changed if k in before_ids and after_ids.get(k) != before_ids[k])
        rec["removed"] = sorted(k for k, v in before.items() if is_data(v) and k not in after)
        # a function / module entry that appeared, disappeared or was replaced (data entries are in changes/removed)
        rec["nondata_changed"] = sorted(k for k in set(before) | set(after)
                                        if ((k in before and not is_data(before[k])) or (k in after and not is_data(after[k])))
                                        and before.get(k) != after.get(k))
        rec["after_digest"] = after_digest
        # per-entry after digests (standalone canon): only to name the entry when a replay does not reproduce it
        rec["after_keys"] = {k: hashlib.sha256(ser(v).encode("utf-8")).hexdigest()[:16] for k, v in after.items()}
        rec["rng"] = rng_states(g) != rng_before
        if exc is not None:
            rec["exception"] = [type(exc).__name__, str(exc)]
        elif kind == "call":
            rec["result"] = Canon().val(result)
        self.cases.setdefault(self.current, []).append(rec)
        if exc is not None:
            raise exc
        return result

    def exec(self, code, g=None, l=None):
        if not isinstance(code, types.CodeType) or l is not None:
            return self.real_exec(code, g, l)
        return self.invoke("exec", code, g, (), None, lambda: self.real_exec(code, g))


def main():
    module, out = sys.argv[1], Path(sys.argv[2])
    only = sys.argv[3] if len(sys.argv) > 3 else None
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(TESTS))
    sys.path.insert(1, str(TESTS.parent / "modkit"))   # as the original suite runner provides (`from pvp import ...`)
    rec = Recorder()
    mod = importlib.import_module(module)
    mod.exec = rec.exec
    real_types = mod.types if hasattr(mod, "types") else types

    class RefFunction:
        def __init__(self, code, g, name=None, argdefs=None, closure=None):
            self.fn = real_types.FunctionType(code, g, name, argdefs, closure)
            self.__code__, self.__globals__, self.__name__ = self.fn.__code__, self.fn.__globals__, self.fn.__name__

        def __call__(self, *a, **k):
            return rec.invoke("call", self.__code__, self.__globals__, a, k, lambda: self.fn(*a, **k))

    proxy = types.SimpleNamespace(**{k: getattr(real_types, k) for k in dir(real_types) if not k.startswith("__")})
    proxy.FunctionType = RefFunction
    mod.types = proxy

    class Result(unittest.TextTestResult):
        def startTest(self, test):
            rec.current = test.id()
            super().startTest(test)

        def stopTest(self, test):
            super().stopTest(test)
            rec.current = None

    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    if only:
        def keep(s):
            out_ = unittest.TestSuite()
            for t in s:
                if isinstance(t, unittest.TestSuite):
                    out_.addTest(keep(t))
                elif only in t.id():
                    out_.addTest(t)
            return out_
        suite = keep(suite)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Result).run(suite)
    src = (TESTS / (module + ".py")).read_bytes()
    doc = dict(module=module, python=sys.version, pyc=str(PYC), pyc_sha256=hashlib.sha256(PYC.read_bytes()).hexdigest(),
               test_source_sha256=hashlib.sha256(src).hexdigest(),
               tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               python_outcome=dict(run=result.testsRun, failures=[t.id() for t, _ in result.failures],
                                   errors=[t.id() for t, _ in result.errors]),
               cases=rec.cases)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("captured", sum(len(v) for v in rec.cases.values()), "invocations in", len(rec.cases), "tests ->", out)


if __name__ == "__main__":
    main()
