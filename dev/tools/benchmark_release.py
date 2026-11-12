"""Reproducible, serial simulation benchmark of pinned release binaries and CPython.

No compilation, product edits, frame presentation, or per-tick JSON output in timed loops.
Usage: python tools/benchmark_release.py --out test_results/performance-YYYYMMDD-HHMMSS
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
PYTHON = REFERENCE / "modkit/tools/python38-embed/python.exe"
SCENARIOS = ("empty", "basic", "zombie_swarm", "projectile_storm", "mixed_late_game")
BACKENDS = ("native_cpp", "python_cppcore", "python_no_cppcore")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def python_trial(args):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    import oracle_record as oracle
    # Original fixture expansion is written to the isolated benchmark folder.
    # The original reference workspace and the existing scenario files stay intact.
    scratch = Path(args.scratch)
    (scratch / "scenarios").mkdir(parents=True, exist_ok=True)
    oracle.HERE = scratch
    scenario = json.loads(Path(args.scenario_file).read_text(encoding="utf-8"))
    scenario["_name"] = args.scenario
    t0, c0 = time.perf_counter(), time.process_time()
    battle = oracle.build(scenario)
    t1, c1 = time.perf_counter(), time.process_time()
    before = battle.engine.native_tick
    per_step = []
    for _ in range(scenario["room_ticks"]):
        start = time.perf_counter()
        battle.step()
        per_step.append(time.perf_counter() - start)
    t2, c2 = time.perf_counter(), time.process_time()
    from pvp import cppcore
    result = {
        "init_seconds": t1 - t0,
        "step_seconds": t2 - t1,
        "step_cpu_seconds": c2 - c1,
        "init_cpu_seconds": c1 - c0,
        "room_ticks": scenario["room_ticks"],
        "native_ticks": battle.engine.native_tick - before,
        "native_ticks_per_second": (battle.engine.native_tick - before) / (t2 - t1),
        "native_dt": getattr(battle.engine, "dt", None),
        "cppcore_available": cppcore.native() is not None,
        "cppcore_installed": getattr(cppcore, "_core", None) is not None,
        "python": sys.version,
        "final_battle_tick": battle.tick,
        "final_result": battle.result,
        "final_units": len(battle.units),
        "room_step_p50_ms": statistics.median(per_step) * 1000,
        "room_step_p95_ms": sorted(per_step)[int(.95 * (len(per_step) - 1))] * 1000,
    }
    battle.close()
    print("BENCH_RESULT " + json.dumps(result, ensure_ascii=False))


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (n, ctypes.c_size_t) for n in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def process_memory(proc):
    if os.name != "nt":
        return {}
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(int(proc._handle)), ctypes.byref(counters), counters.cb)
    return ({"peak_working_set_mb": counters.PeakWorkingSetSize / 1048576,
             "peak_private_commit_mb": counters.PeakPagefileUsage / 1048576} if ok else {})


def summarize(rows):
    groups = []
    for scene in SCENARIOS:
        group = {"scenario": scene, "backends": {}}
        for backend in BACKENDS:
            runs = [r for r in rows if r["scenario"] == scene and r["backend"] == backend and not r["warmup"]]
            if not runs:
                continue
            times = [r["step_seconds"] for r in runs]
            group["backends"][backend] = {
                "runs": len(runs), "median_step_seconds": statistics.median(times),
                "min_step_seconds": min(times), "max_step_seconds": max(times),
                "median_init_seconds": statistics.median(r["init_seconds"] for r in runs),
                "median_peak_working_set_mb": statistics.median(r.get("peak_working_set_mb", 0) for r in runs),
                "room_ticks": runs[0]["room_ticks"],
                "median_ms_per_room_tick": 1000 * statistics.median(times) / runs[0]["room_ticks"],
            }
        native = group["backends"].get("native_cpp")
        if native:
            for backend in BACKENDS[1:]:
                if backend in group["backends"]:
                    group["backends"][backend]["time_divided_by_native"] = group["backends"][backend]["median_step_seconds"] / native["median_step_seconds"]
        groups.append(group)
    return groups


def main(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "scenarios").mkdir()
    (out / "logs").mkdir()
    pinned = json.loads((ROOT / "test_results/codex-resume-20261102-220027/verified-binaries98/SHA256.json").read_text("utf-8"))
    exe = ROOT / "build/Release/run_battle.exe"
    hashes = {str(p): sha(p) for p in (exe, ROOT / "build/Release/PvZPvPNative.exe", ROOT / "dist/PvZ-PvP-Native-20261104-workerfix-r2/PvZPvPNative.exe")}
    assert hashes[str(exe)] == pinned["run_battle.exe"]
    assert hashes[str(ROOT / "dist/PvZ-PvP-Native-20261104-workerfix-r2/PvZPvPNative.exe")] == pinned["PvZPvPNative.exe"]
    original_inputs = {}
    scenarios = {}
    for name in SCENARIOS:
        original = ROOT / "tools/scenarios" / (name + ".json")
        expanded = original.with_name("_expanded_" + original.name)
        original_inputs[str(original)] = sha(original)
        if expanded.exists():
            original_inputs[str(expanded)] = sha(expanded)
        py_config = json.loads(original.read_text("utf-8"))
        cpp_config = json.loads((expanded if expanded.exists() else original).read_text("utf-8"))
        if name == "empty":
            py_config["room_ticks"] = cpp_config["room_ticks"] = 300
        assert not py_config.get("inputs") and not cpp_config.get("inputs"), "--bench intentionally does not dispatch input schedules"
        for backend in BACKENDS:
            path = out / "scenarios" / (name + "-" + backend + ".json")
            save(path, cpp_config if backend == "native_cpp" else py_config)
            scenarios[(name, backend)] = path
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PVZ_", "PVP_")):
            env.pop(key)
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    metadata = {
        "created_at": datetime.datetime.now().astimezone().isoformat(),
        "release": "20261104-workerfix-r2", "platform": platform.platform(),
        "executable_hashes": hashes, "original_scenario_hashes": original_inputs,
        "benchmark_script_sha256": sha(__file__), "repeats": args.repeats,
        "warmup_runs_per_scenario_and_backend": 1,
        "scope": "Whole-battle step loop; excludes startup, map construction, JSON tracing, screen presentation, network transport and replay compression. Native executable is the exact final build98 acceptance runner linked to the release product libraries.",
        "backend_order": "rotated by round, no concurrent benchmarks",
        "environment": {k: env[k] for k in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "PYTHONDONTWRITEBYTECODE")},
    }
    save(out / "metadata.json", metadata)
    rows = []
    for round_no in range(args.repeats + 1):
        for scene in SCENARIOS:
            order = BACKENDS[round_no % 3:] + BACKENDS[:round_no % 3]
            for backend in order:
                name = "%s-%s-r%d" % (scene, backend, round_no)
                run_env = env.copy()
                run_env.update(APPDATA=str(out / "userdata" / name), PVP_USERDATA=str(out / "userdata" / name / "pvp"))
                path = scenarios[(scene, backend)]
                if backend == "native_cpp":
                    cmd = [str(exe), str(path), "--bench"]
                else:
                    on = "1" if backend == "python_cppcore" else "0"
                    run_env.update(PVP_CPP=on, PVP_NATIVE=on)
                    cmd = [str(PYTHON), str(Path(__file__).resolve()), "--python-trial", "--scenario", scene, "--scenario-file", str(path), "--scratch", str(out / "scratch" / name)]
                log = out / "logs" / (name + ".log")
                start = time.perf_counter()
                mem = {}
                with log.open("w", encoding="utf-8") as fh:
                    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=run_env, stdout=fh, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    while proc.poll() is None:
                        for k, v in process_memory(proc).items():
                            mem[k] = max(mem.get(k, 0), v)
                        if time.perf_counter() - start > 180:
                            proc.kill()
                            proc.wait()
                            raise RuntimeError("Benchmark timed out: " + name)
                        time.sleep(.1)
                raw = log.read_text(encoding="utf-8", errors="replace")
                if proc.returncode:
                    raise RuntimeError("Benchmark failed: " + name + "\n" + raw[-2000:])
                if backend == "native_cpp":
                    match = re.search(r"init ([0-9.]+)s, (\d+) room ticks ([0-9.]+)s", raw)
                    if not match:
                        raise RuntimeError("Missing native timing: " + name)
                    result = dict(init_seconds=float(match[1]), room_ticks=int(match[2]), step_seconds=float(match[3]))
                else:
                    result = json.loads(next(line.split("BENCH_RESULT ", 1)[1] for line in raw.splitlines() if line.startswith("BENCH_RESULT ")))
                    assert result["cppcore_available"] == (backend == "python_cppcore"), result
                result.update(scenario=scene, backend=backend, round=round_no, warmup=round_no == 0, process_wall_seconds=time.perf_counter() - start, log=str(log.relative_to(out)), **mem)
                rows.append(result)
                with (out / "runs.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(result, ensure_ascii=False) + "\n")
                save(out / "summary.json", {"complete": False, "groups": summarize(rows), "completed_runs": len(rows)})
                print("%02d %-18s %-18s init=%.3f step=%.3f peak=%.1fMB%s" % (round_no, scene, backend, result["init_seconds"], result["step_seconds"], mem.get("peak_working_set_mb", 0), " WARMUP" if round_no == 0 else ""), flush=True)
    changes = [p for p, h in {**hashes, **original_inputs}.items() if sha(p) != h]
    save(out / "summary.json", {"complete": True, "groups": summarize(rows), "completed_runs": len(rows), "inputs_changed": changes, "success": not changes})
    if changes:
        raise RuntimeError("Pinned inputs changed during benchmarking: " + str(changes))
    print("BENCHMARK_COMPLETE " + str(out), flush=True)


if __name__ == "__main__":
    if '--baseline-manifest' in sys.argv:
        from benchmark_pvp72 import main as compare_manifests
        compare_manifests()
        raise SystemExit(0)
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--python-trial", action="store_true")
    parser.add_argument("--scenario")
    parser.add_argument("--scenario-file")
    parser.add_argument("--scratch")
    args = parser.parse_args()
    if args.python_trial:
        python_trial(args)
    else:
        main(args)
