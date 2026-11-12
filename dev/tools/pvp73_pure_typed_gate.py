"""PvP73 pure-typed gate: the shipped dynamic battle path must run without the V runtime.

Runs real app matches through app_run (the same translated app, Room and TypedBattle the game
ships) and reads TypedBattle.backend_audit()['dynamic_v_work']: V boxes allocated and V calls
dispatched on the calling thread *inside* the typed dynamic entry points

    step           TypedSession::step loop (the 250 Hz battle)
    command_input  TypedSession::command (validated player/AI inputs)
    ai_tick        typed AI observe + plan + control (its AISeat.send -> Room.command
                   boundary is measured separately and excluded)

Every entry must have run (entries > 0) and every counter must be exactly 0. Cold construction,
Room/UI and the per-frame presentation snapshot are outside these entries by design.

    python tools/pvp73_pure_typed_gate.py --out <dir> [--app-run build/app-typed72-v2/Release/app_run.exe]
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    # name, app_run arguments, entries that must have run
    ("duel_ai", ["airoom", "40"], ("step", "command_input", "ai_tick")),
    ("coop_ai", ["cooplobby"], ("step", "command_input", "ai_tick")),
    ("duo_ai", ["script", str(ROOT / "tools/pvp73_gate_duo.json")], ("step", "command_input", "ai_tick")),
]


def run(app_run, name, args, out, timeout):
    work = out / name
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PVP_USERDATA=str(work / "userdata"), SDL_AUDIODRIVER="dummy")
    started = time.time()
    try:
        proc = subprocess.run([str(app_run)] + args + ([str(work)] if args[0] in ("cooplobby", "script") else []), cwd=str(ROOT), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        text, rc = proc.stdout.decode("utf-8", "replace"), proc.returncode
    except subprocess.TimeoutExpired as error:
        text, rc = (error.stdout or b"").decode("utf-8", "replace"), "TIMEOUT"
    (work / "stdout.txt").write_text(text, encoding="utf-8")
    audits = [json.loads(line.split(" ", 1)[1]) for line in text.splitlines() if line.startswith("PURE_TYPED_AUDIT ")]
    marker = "call room.battle.backend_audit -> "
    audits += [json.loads(line.split(marker, 1)[1]) for line in text.splitlines() if marker in line]
    return rc, audits, round(time.time() - started, 1)


def check(audit, required):
    problems = []
    if audit.get("backend") != "typed72" or not audit.get("session"):
        problems.append("battle is not a live typed72 session")
    if not audit.get("typed_steps"):
        problems.append("no typed steps")
    work = audit.get("dynamic_v_work")
    if not isinstance(work, dict):
        return problems + ["backend_audit has no dynamic_v_work (gate instrumentation missing)"]
    for entry in required:
        row = work.get(entry)
        if not row or not row.get("entries"):
            problems.append("entry %s never ran" % entry)
    # Negative control: the counters must be alive (the room/UI around the battle does use V).
    if not (audit.get("v_activity_total") or {}).get("calls"):
        problems.append("V activity counters read zero overall (instrumentation not live)")
    for entry, row in work.items():
        if row.get("boxes") or row.get("calls"):
            problems.append("%s: %d V boxes, %d V calls" % (entry, row.get("boxes", 0), row.get("calls", 0)))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--app-run", default=str(ROOT / "build/app-typed72-v2/Release/app_run.exe"))
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, app_args, required in SCENARIOS:
        rc, audits, seconds = run(args.app_run, name, app_args, out, args.timeout)
        problems = [] if audits else ["no PURE_TYPED_AUDIT line (run failed or ended before the battle)"]
        if audits:
            problems += check(audits[-1], required)
        rows.append(dict(scenario=name, rc=rc, seconds=seconds, passed=not problems, problems=problems,
                         audit=audits[-1] if audits else None))
        print(name, "PASS" if not problems else "FAIL", problems, flush=True)
    summary = dict(gate="pvp73-pure-typed-dynamic-path", passed=all(r["passed"] for r in rows), scenarios=rows)
    (out / "pure-typed-gate.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
