"""Which Python functions run inside NativeBattle.step() (and how often) across
reference scenarios. Output extract/schema/step_coverage.json:
  {"file:function:line": [calls, source_lines]}  sorted by file."""
import sys, os, json, collections, inspect
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit"), str(REF / "cpp_port" / "tools")]
    os.chdir(str(REF))
    os.environ["PVP_CPP"] = "0"; os.environ["PVP_NATIVE"] = "0"
    import multiworker_fixtures as F
    import pvp70_workload, pvp64_workload
    calls = collections.Counter()
    sizes = {}

    def prof(frame, event, arg):
        if event == "call":
            c = frame.f_code
            fn = c.co_filename
            if "modkit" in fn or "original-1.5.0.1" in fn or "pvzrouge" in fn:
                key = "%s:%s:%d" % (Path(fn).name, c.co_name, c.co_firstlineno)
                calls[key] += 1
                if key not in sizes:
                    try:
                        sizes[key] = len(inspect.getsourcelines(c)[0])
                    except Exception:
                        sizes[key] = -1
    scen = [("zombie_swarm", lambda: _mk(F, F.zombie_swarm)), ("projectile_storm", lambda: _mk(F, F.projectile_storm)),
            ("mixed_late_game", lambda: _mk(F, F.mixed_late_game)), ("starfruit", lambda: _mk(F, F.starfruit_late_game)),
            ("pvp70", pvp70_workload.battle)]
    for name, mk in scen:
        b = mk()
        sys.setprofile(prof)
        try:
            for i in range(60):
                b.step()
        finally:
            sys.setprofile(None)
        b.close()
        print("done", name, flush=True)
    out = {k: [calls[k], sizes.get(k, -1)] for k in sorted(calls)}
    (ROOT / "extract/schema/step_coverage.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for k, (n, s) in out.items():
        f = k.split(":")[0]
        per[f][0] += 1; per[f][1] += max(s, 0); per[f][2] += n
    sys.stdout.reconfigure(encoding="utf-8")
    for f, (nf, ns, nc) in sorted(per.items(), key=lambda x: -x[1][1]):
        print("%-40s funcs=%4d lines=%6d calls=%9d" % (f, nf, ns, nc))


def _mk(F, fn):
    b = F.new_battle(seed=7)
    F.durable_heroes(b)
    fn(b)
    return b


if __name__ == "__main__":
    main()
