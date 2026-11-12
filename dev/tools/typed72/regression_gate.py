#!/usr/bin/env python3
"""Serial, fail-closed typed72 regression gate (Python 3.8+, standard library).

Examples (run from the repository, while no compiler/audit is running)::
    python -B tools/typed72/regression_gate.py --out test_results/gate-r5
    python -B tools/typed72/regression_gate.py --out test_results/gate-r5 --resume
    python -B tools/typed72/regression_gate.py --phase sim --scenario supp_actions \
        --out test_results/gate-actions
    python -B tools/typed72/regression_gate.py --phase all --scenario supp_actions \
        --record-unfrozen --out test_results/gate-actions-all
    python -B tools/typed72/regression_gate.py --out test_results/gate-production \
        --typed-exe build/app-typed72-v2/Release/typed72_match_gate.exe --require-production

The fixed manifest is the 58 *.cmp.json names in frames-f7. Frozen frame/snapshot
references are opened read-only, never copied, regenerated, or removed. Only an
explicit --scenario outside that manifest plus --record-unfrozen permits a new
frame/snapshot V recording. Simulation always records V independently (v2).

Each case gets an immutable attempt directory; retries do not overwrite failures.
PASS traces/atlases are discarded unless --keep-pass-artifacts is given. A resume
rehashes selected source trees, generators, tools, binaries, scenarios and frozen
references with SHA-256, then checks saved PASS evidence before skipping it. Drift
is an ERROR requiring a fresh output directory, not permission to bless old PASS.
JSONL comparison holds only one record per side, with bounded diagnostics. Final
settlement JSON (including its ordered event log) is loaded separately.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
SCHEMA = "typed72-regression-gate-v1"
TOL = 1e-9
PHASES = ("sim", "frames", "snapshots")
SKIP_SNAPSHOT = frozenset(("native_frame", "engine_load"))
SOURCE_SUFFIXES = frozenset((".c", ".cc", ".cpp", ".h", ".hh", ".hpp", ".inc",
                             ".inl", ".py", ".ps1", ".sh", ".json", ".cmake", ".txt"))
PRUNE_DIRS = frozenset(("build", "build-zi", "__pycache__", ".git", "node_modules",
                        "test_results", "dist", "history", "archive", "backups"))
MAX_DETAILS = 25


class GateError(Exception):
    """An execution/input error, as opposed to a valid but unequal comparison."""


class GateFailure(GateError):
    """A comparison or process/report contract failed."""


def require(condition, message, error=GateError):
    if not condition:
        raise error(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number_equal(a, b, nan_equal=False):
    # Never evaluate inf <= tolerance * inf. Equal infinities have equal signs.
    # Only the simulation walk historically permits paired NaNs; frame/snapshot
    # comparisons must continue to reject them, even on both sides.
    if a == b:
        return True
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    if isinstance(a, float) and not math.isfinite(a):
        return nan_equal and isinstance(b, float) and math.isnan(a) and math.isnan(b)
    if isinstance(b, float) and not math.isfinite(b):
        return False
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def brief(value):
    text = repr(value)
    return text if len(text) <= 400 else text[:397] + "..."


def first_difference(a, b, path="", skip=frozenset()):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return None if number_equal(a, b) else (path, brief(a), brief(b))
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a:
            if key in skip:
                continue
            here = path + "." + key
            if key not in b:
                return (here, "<present>", "<missing>")
            diff = first_difference(a[key], b[key], here, skip)
            if diff is not None:
                return diff
        for key in b:
            if key not in a and key not in skip:
                return (path + "." + key, "<missing>", "<present>")
        return None
    if isinstance(a, list) and isinstance(b, list):
        # Intentionally do NOT turn ID-bearing lists into dicts: order and every
        # duplicate occurrence are part of the observable snapshot contract.
        if len(a) != len(b):
            return (path + "#length", len(a), len(b))
        for index, (left, right) in enumerate(zip(a, b)):
            diff = first_difference(left, right, path + "/" + str(index), skip)
            if diff is not None:
                return diff
        return None
    return None if type(a) is type(b) and a == b else (path, brief(a), brief(b))


def check_snapshot_ids(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in SKIP_SNAPSHOT:
                check_snapshot_ids(item, path + "." + key)
    elif isinstance(value, list):
        if value and all(isinstance(item, dict) and "id" in item for item in value):
            seen = set()
            for item in value:
                key = item["id"]
                require(isinstance(key, (str, int)) and not isinstance(key, bool),
                        "invalid snapshot id at " + path)
                require(key not in seen, "duplicate snapshot id %r at %s" % (key, path))
                seen.add(key)
        for index, item in enumerate(value):
            check_snapshot_ids(item, path + "/" + str(index))


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=object_pairs)


def read_json(path):
    path = Path(path)
    require(path.is_file(), "missing JSON/report: " + str(path))
    try:
        with path.open(encoding="utf-8-sig") as stream:
            return loads(stream.read())
    except (ValueError, OSError) as exc:
        raise GateError("invalid JSON %s: %s" % (path, exc))


def sha256(path):
    path = Path(path)
    require(path.is_file(), "missing fingerprint input: " + str(path))
    before = stat_signature([path])
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    require(stat_signature([path]) == before, "fingerprint input changed while hashing: " + str(path))
    return digest.hexdigest()


def digest_json(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temp), str(path))


class BoundedDifferences(list):
    def __init__(self):
        super().__init__()
        self.total = 0
        self.gaps = 0

    def append(self, item):
        self.total += 1
        if item[0].startswith("only_in"):
            self.gaps += 1
        if len(self) < MAX_DETAILS:
            super().append((item[0], item[1], brief(item[2]), brief(item[3])))


def load_sim_contract(path):
    """Reuse compare_match.walk's intentional V exemptions, not its main()."""
    spec = importlib.util.spec_from_file_location("typed72_legacy_contract", str(path))
    require(spec is not None and spec.loader is not None, "cannot load simulation contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.walk

    def safe_walk(a, b, field, out):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if not number_equal(a, b, nan_equal=True):
                out.append(("diff", field, a, b))
            return
        original(a, b, field, out)

    # Original recursion resolves module.walk, so nested numbers are fixed too.
    module.walk = safe_walk
    return module


def sim_difference(a, b, contract):
    keys = ("t", "g", "avatars", "inp", "battle", "rng", "players")
    for side, value in (("reference", a), ("typed", b)):
        require(all(key in value for key in keys), side + " simulation record lacks required fields")
        require(isinstance(value["players"], dict), side + " players is not an object")
        require(all(isinstance(p, dict) for p in value["players"].values()), "invalid player record")
    found = BoundedDifferences()
    contract.walk({key: a[key] for key in keys[:-1]},
                  {key: b[key] for key in keys[:-1]}, "", found)
    players = {side: {field: player.get(field) for field in contract.PLAYER_FIELDS}
               for side, player in a["players"].items()}
    contract.walk(players, b["players"], ".players", found)
    return None if not found.total else {"count": found.total, "field_gaps": found.gaps,
                                         "differences": list(found)}


def records(path, phase):
    """Validate even the unpaired tail; JSONL order is never sorted or deduplicated."""
    previous = None
    with Path(path).open(encoding="utf-8-sig") as stream:
        for lineno, line in enumerate(stream, 1):
            require(line.strip(), "%s:%d blank trace record" % (path, lineno))
            try:
                row = loads(line)
                require(isinstance(row, dict), "trace record is not an object")
                if phase == "frames":
                    payload = row["frame"]
                    tick = payload["tick"]
                    require(isinstance(payload["commands"], list), "frame commands is not a list")
                    require(isinstance(payload["positions"], (dict, list)), "invalid frame positions")
                elif phase == "snapshots":
                    tick, payload = row["rt"], row["snapshot"]
                    require(isinstance(payload, dict), "snapshot is not an object")
                    require(integer(payload["tick"]), "invalid snapshot.tick")
                    check_snapshot_ids(payload)
                else:
                    tick, payload = row["t"], row
                first = -1 if phase == "snapshots" else 0
                require(integer(tick, first), "invalid tick: " + repr(tick))
                require(previous is not None or tick == first, "trace must start at tick %d" % first)
                if previous is not None:
                    require(tick > previous, "duplicate/out-of-order tick %s after %s" % (tick, previous))
                    if phase != "frames":
                        require(tick == previous + 1, "missing tick between %s and %s" % (previous, tick))
                previous = tick
            except (KeyError, TypeError, ValueError, GateError) as exc:
                raise GateError("%s:%d: %s" % (path, lineno, exc))
            yield tick, payload


def compare_stream(reference, typed, phase, contract=None):
    require(phase in PHASES, "unknown comparison phase")
    require(Path(reference).is_file() and Path(typed).is_file(), "missing comparison trace")
    result = {"phase": phase, "reference_lines": 0, "typed_lines": 0,
              "compared": 0, "equal_records": 0, "missing_ticks": 0, "extra_ticks": 0,
              "first_difference": None, "last_reference_tick": None, "last_typed_tick": None}
    left, right = records(reference, phase), records(typed, phase)
    try:
        for a, b in itertools.zip_longest(left, right):
            if a is not None:
                result["reference_lines"] += 1
                result["last_reference_tick"] = a[0]
            if b is not None:
                result["typed_lines"] += 1
                result["last_typed_tick"] = b[0]
            if a is None or b is None:
                result["extra_ticks" if a is None else "missing_ticks"] += 1
                diff = {"kind": "extra_tick" if a is None else "missing_tick",
                        "reference_tick": a[0] if a else None, "typed_tick": b[0] if b else None}
            elif a[0] != b[0]:
                # Positional lockstep intentionally fails alignment, rather than hiding
                # a missing+extra pair behind equal aggregate line counts.
                diff = {"kind": "tick_mismatch", "reference_tick": a[0], "typed_tick": b[0]}
            else:
                result["compared"] += 1
                if phase == "sim":
                    require(contract is not None, "simulation contract not loaded")
                    diff = sim_difference(a[1], b[1], contract)
                else:
                    skip = SKIP_SNAPSHOT if phase == "snapshots" else frozenset()
                    diff = first_difference(a[1], b[1], skip=skip)
                if diff is None:
                    result["equal_records"] += 1
                else:
                    diff = {"kind": "value_difference", "tick": a[0], "detail": diff}
            if diff is not None and result["first_difference"] is None:
                result["first_difference"] = diff
    finally:
        left.close()
        right.close()
    result["identical"] = (result["reference_lines"] > 0 and result["typed_lines"] > 0
                            and result["first_difference"] is None
                            and result["equal_records"] == result["reference_lines"] == result["typed_lines"])
    if not result["reference_lines"] or not result["typed_lines"]:
        result["first_difference"] = {"kind": "empty_trace"}
    return result


def validate_match_report(report, returncode, require_production=False):
    require(type(returncode) is int and returncode == 0,
            "match process rc is not zero: %r" % returncode, GateFailure)
    require(isinstance(report, dict) and report, "missing/empty match report")
    require(report.get("backend_requested") == "typed72-integrated", "missing/invalid backend_requested", GateFailure)
    require(report.get("backend_actual") in ("typed72-probe-composition-e1", "typed72-app-composition-e2",
                                              "typed72-stripped-composition-e2"),
            "missing/unknown backend_actual", GateFailure)
    require(type(report.get("production_composition")) is bool,
            "missing/non-bool production_composition", GateFailure)
    if require_production:
        require(report["backend_actual"] == "typed72-app-composition-e2"
                and report["production_composition"] is True,
                "--require-production needs typed72-app-composition-e2 and production_composition=true", GateFailure)
    require("failure" in report and report["failure"] == "", "match report failure is not empty", GateFailure)
    require(type(report.get("fallback_count")) is int and report["fallback_count"] == 0,
            "missing/nonzero fallback_count", GateFailure)
    require(report.get("unsupported_operations") == [], "missing/nonempty unsupported_operations", GateFailure)
    require(report.get("unsupported_draws") == {}, "missing/nonempty unsupported_draws", GateFailure)
    for key in ("typed_step_count", "native_tick_count"):
        require(integer(report.get(key)), "missing/invalid report " + key)
    for key, value in report.items():
        lower = key.lower()
        if "unsupported" in lower or "fallback" in lower:
            require(value in (0, [], {}, False, ""), "nonzero report " + key, GateFailure)
        if lower in ("rc", "returncode", "return_code", "exit_code"):
            require(type(value) is int and value == 0, "nonzero report " + key, GateFailure)


def compare_final(reference, typed, contract):
    a, b = read_json(reference), read_json(typed)
    for side, value in (("reference", a), ("typed", b)):
        require(isinstance(value, dict) and all(k in value for k in ("tick", "log", "result")),
                side + " final lacks tick/log/result")
        require(integer(value["tick"]), side + " final invalid tick")
        require(isinstance(value["log"], list) and value["log"], side + " final log empty/invalid")
        require(all(isinstance(e, dict) and isinstance(e.get("event"), str) for e in value["log"]),
                side + " final invalid log event")
    found = BoundedDifferences()
    contract.walk(a["log"], b["log"], ".log", found)
    return {"tick_equal": a["tick"] == b["tick"], "ticks": [a["tick"], b["tick"]],
            "result_equal": a["result"] == b["result"],
            "log_equal": found.total == 0, "log_lengths": [len(a["log"]), len(b["log"])],
            "log_difference_count": found.total, "log_differences": list(found)}


def validate_comparison(value, report, returncode, require_production=False):
    validate_match_report(report, returncode, require_production)
    require(isinstance(value, dict) and value.get("identical") is True,
            "comparison is not identical", GateFailure)
    require(type(value.get("typed_rc")) is int and value["typed_rc"] == 0,
            "comparison typed_rc is missing/nonzero", GateFailure)
    counts = [value.get(k) for k in ("reference_lines", "typed_lines", "compared", "equal_records")]
    require(all(integer(n, 1) for n in counts) and len(set(counts)) == 1,
            "comparison has empty/unequal counts", GateFailure)
    require(value.get("first_difference") is None and value.get("missing_ticks") == 0
            and value.get("extra_ticks") == 0, "comparison has tick/value differences", GateFailure)
    phase = value.get("phase")
    require(phase in PHASES, "invalid comparison phase")
    if phase == "sim":
        require(counts[0] == report["native_tick_count"] + 1,
                "simulation count disagrees with native_tick_count", GateFailure)
        final = value.get("final") or {}
        require(all(final.get(k) is True for k in ("tick_equal", "log_equal", "result_equal")),
                "final tick/log/result differs or is missing", GateFailure)
        require(final.get("log_difference_count") == 0 and final.get("log_differences") == [],
                "final log differences", GateFailure)
        require(final.get("ticks") == [report["typed_step_count"]] * 2,
                "final tick disagrees with typed_step_count", GateFailure)
        lengths = final.get("log_lengths")
        require(isinstance(lengths, list) and len(lengths) == 2
                and all(integer(n, 1) for n in lengths) and lengths[0] == lengths[1],
                "empty/unequal final logs", GateFailure)
        require(value.get("last_typed_tick") == report["native_tick_count"],
                "last simulation tick disagrees with report", GateFailure)
    elif phase == "frames":
        require(integer(value.get("last_typed_tick"))
                and value["last_typed_tick"] <= report["native_tick_count"],
                "last frame exceeds native_tick_count", GateFailure)


def fixed_names(root):
    directory = root / "test_results/typed72-20261108/frames-f7"
    names = sorted(p.name[:-9] for p in directory.glob("*.cmp.json") if p.is_file())
    require(len(names) == 58 and len(set(names)) == 58,
            "fixed frames-f7 manifest must contain exactly 58 scenarios, found %d" % len(names))
    return names


def scenario_path(root, name):
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) is not None,
            "unsafe scenario name: " + name)
    for path in (root / "build/typed72-match-v1/scenarios" / (name + ".json"),
                 root / "tools/scenarios" / ("_expanded_" + name + ".json"),
                 root / "tools/scenarios" / (name + ".json")):
        if path.is_file():
            return path.resolve()
    raise GateError("missing scenario: " + name)


def executables(root, phase, recording, typed_exe=None):
    stage = root / "build/typed72-match-v1"
    result = {"export": stage / "build/Release/cold72_export.exe",
              "match": typed_exe or stage / "build/Release/match72.exe"}
    if phase == "sim" or recording:
        version = {"sim": 2, "frames": 3, "snapshots": 4}[phase]
        result["record"] = root / ("build/typed72-ref-recorder-v%d/build/Release/ref72_record.exe" % version)
    return result


def source_files(root, recorder_versions):
    # Deliberately bounded roots, never root.rglob/build.rglob: those contain huge
    # historical stages, atlas blobs and previous test_results trees.
    trees = [(root / "src", set()), (root / "tools/typed72", set()),
             (root / "build/typed72-match-v1", {"scenarios"}),
             (root / "build/typed72-integrated-v44/source", set())]
    trees.extend((root / ("build/typed72-ref-recorder-v%d" % version), set())
                 for version in sorted(recorder_versions))
    if (root / "cmake").is_dir():
        trees.append((root / "cmake", set()))
    result = set()
    for base, extra_prune in trees:
        require(base.is_dir(), "missing source tree: " + str(base))
        for directory, dirs, files in os.walk(str(base), followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in PRUNE_DIRS and d not in extra_prune
                             and not d.lower().startswith((".bak", "backup", "history")))
            for name in files:
                path = Path(directory) / name
                if path.suffix.lower() in SOURCE_SUFFIXES and ".bak" not in name.lower():
                    result.add(path)
    for rel in ("CMakeLists.txt", "build/typed72-integrated-v44/integration-manifest.json"):
        path = root / rel
        require(path.is_file(), "missing required generation input: " + str(path))
        result.add(path)
    require(result, "no source files to fingerprint")
    return sorted(result, key=lambda p: p.as_posix())


def fingerprint_files(paths, root):
    result = {}
    for path in paths:
        resolved = path.resolve()
        try:
            label = resolved.relative_to(root).as_posix()
        except ValueError:
            label = str(resolved)
        result[label] = sha256(resolved)
    return result


def stat_signature(paths):
    return {str(path): (path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ctime_ns)
            for path in paths}


def linked_inputs(root, typed_exe):
    # These are the actual imported libraries in exporter/recorder CMakeLists,
    # NOT proof that those libraries were rebuilt from today's source files.
    result = [root / ("build/Release/" + name) for name in
              ("pvzcore.lib", "pvzui.lib", "pvzsnapshot_zlib.lib")]
    if typed_exe is None:
        result.append(root / "build/typed72-integrated-v44/build-zi/Release/pvztyped72.lib")
    else:
        # Production --typed-exe links this app kernel rather than typed_lib.
        kernel = typed_exe.parent / "pvztyped72kernel.lib"
        if kernel.is_file():
            result.append(kernel)
    return result


def build_plan(root, phases, names, fixed, record_unfrozen, typed_exe=None):
    plan = []
    for phase in phases:
        for name in names:
            source = scenario_path(root, name)
            frozen = phase != "sim" and name in fixed
            recording = phase != "sim" and not frozen
            require(not recording or record_unfrozen,
                    "%s/%s has no frozen reference; explicitly use --record-unfrozen" % (phase, name))
            reference = None
            if frozen:
                folder, suffix = (("frames-f7", ".frames.jsonl") if phase == "frames"
                                  else ("snap-s3", ".snap.jsonl"))
                reference = root / "test_results/typed72-20261108" / folder / (name + suffix)
                require(reference.is_file() and reference.stat().st_size > 0,
                        "missing/empty frozen reference (will NOT re-record): " + str(reference))
            plan.append({"phase": phase, "name": name, "source": source, "reference": reference,
                         "recording": recording, "executables": executables(root, phase, recording, typed_exe)})
    return plan


def within(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_output_location(root, output):
    require(output != root and not within(root, output), "output must not contain the repository")
    for rel in ("src", "tools", "build", "test_results/typed72-20261108/frames-f7",
                "test_results/typed72-20261108/snap-s3"):
        protected = root / rel
        require(not within(output, protected) and not within(protected, output),
                "output overlaps protected input tree: " + rel)


def checked_artifact(output, attempt, path):
    # Resolve before unlink, and reject both symlink files and symlink ancestors
    # escaping the owned attempt. Never remove a directory or a frozen reference.
    output, attempt, path = Path(output).resolve(), Path(attempt).resolve(), Path(path)
    require(within(attempt, output) and attempt != output, "attempt is outside owned output")
    resolved = path.resolve()
    require(not path.is_symlink() and within(resolved, attempt) and resolved != attempt,
            "unsafe artifact path: " + str(path))
    require(resolved.is_file(), "artifact is not a regular file: " + str(resolved))
    return resolved


def cleanup_pass(output, attempt, paths):
    for path in paths:
        if Path(path).exists():
            checked_artifact(output, attempt, path).unlink()


def run_process(command, root, env, timeout, log, command_rows):
    row = {"command": [str(value) for value in command], "log": str(log), "status": "RUNNING"}
    command_rows.append(row)
    started = time.monotonic()
    try:
        with Path(log).open("xb") as stream:
            result = subprocess.run(row["command"], cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        row.update(rc=result.returncode, status="PASS" if result.returncode == 0 else "FAIL")
        require(result.returncode == 0, "%s exited rc=%d; see %s" %
                (Path(command[0]).name, result.returncode, log), GateFailure)
        return result.returncode
    except subprocess.TimeoutExpired:
        row.update(status="ERROR", error="TIMEOUT", timeout_seconds=timeout)
        raise GateError("TIMEOUT after %s seconds: %s; see %s" % (timeout, command[0], log))
    finally:
        row["elapsed_seconds"] = round(time.monotonic() - started, 3)


def clean_environment(attempt):
    env = dict(os.environ)
    for key in list(env):
        if key.upper().startswith(("MATCH_", "REF_")):
            del env[key]
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONIOENCODING="utf-8",
               PVP_USERDATA=str(attempt / "userdata"))
    return env


def execute_case(root, output, item, attempt, row, timeout, keep, contract, require_production=False):
    phase, source, tools = item["phase"], item["source"], item["executables"]
    cold, atlas = attempt / "cold.json", attempt / "atlas.bin"
    trace, report_path, final_path = (attempt / "typed.jsonl", attempt / "report.json",
                                       attempt / "typed.final.json")
    env = clean_environment(attempt)
    run_process([tools["export"], source, cold, atlas], root, env, timeout,
                attempt / "export.log", row["commands"])
    require(cold.is_file() and atlas.is_file(), "export did not produce cold.json/atlas.bin")
    reference = item["reference"]
    deletable = [atlas, attempt / "atlas.bin.draw.json", attempt / "atlas.bin.recipes.json", trace]
    if phase == "sim" or item["recording"]:
        reference_trace = attempt / "reference.jsonl"
        ref_env = dict(env, PVP_USERDATA=str(attempt / "userdata-reference"))
        if phase == "sim":
            reference = reference_trace
        else:
            reference = attempt / ("reference.frames.jsonl" if phase == "frames" else "reference.snap.jsonl")
            ref_env["REF_FRAMES" if phase == "frames" else "REF_SNAPSHOTS"] = str(reference)
        run_process([tools["record"], source, reference_trace], root, ref_env, timeout,
                    attempt / "record.log", row["commands"])
        deletable.extend([reference_trace, reference])
    typed = trace
    if phase != "sim":
        typed = attempt / ("typed.frames.jsonl" if phase == "frames" else "typed.snap.jsonl")
        env["MATCH_FRAMES" if phase == "frames" else "MATCH_SNAPSHOTS"] = str(typed)
        env["MATCH_NO_TRACE"] = "1"
        deletable.append(typed)
    rc = run_process([tools["match"], cold, atlas, source, trace, report_path, final_path],
                     root, env, timeout, attempt / "match.log", row["commands"])
    report = read_json(report_path)
    if isinstance(report, dict):
        row["backend_actual"] = report.get("backend_actual")
        row["production_composition"] = report.get("production_composition")
    validate_match_report(report, rc, require_production)
    comparison = compare_stream(reference, typed, phase, contract)
    comparison["typed_rc"] = rc
    if phase == "sim":
        comparison["final"] = compare_final(attempt / "reference.jsonl.final.json", final_path, contract)
        comparison["identical"] = comparison["identical"] and all(
            comparison["final"][key] for key in ("tick_equal", "result_equal", "log_equal"))
    if phase == "snapshots":
        ticks = read_json(source).get("room_ticks", 30)
        require(integer(ticks), "invalid scenario room_ticks")
        require(comparison["reference_lines"] == comparison["typed_lines"] == ticks + 1,
                "snapshot count differs from scenario room_ticks + 1", GateFailure)
    compare_path = attempt / "comparison.json"
    atomic_json(compare_path, comparison)
    row["comparison"] = {k: comparison[k] for k in
                         ("reference_lines", "typed_lines", "equal_records", "first_difference")}
    validate_comparison(comparison, report, rc, require_production)
    evidence = [compare_path, report_path, final_path]
    if phase == "sim":
        evidence.append(attempt / "reference.jsonl.final.json")
    row["evidence"] = {p.relative_to(output).as_posix(): sha256(p) for p in evidence}
    # Trace hashes remain useful even when PASS cleanup discards large files.
    row["trace_sha256"] = {"reference": sha256(reference), "typed": sha256(typed)}
    row["typed_rc"] = rc
    row["cleanup_pending"] = [str(p) for p in set(deletable)] if not keep else []


def verify_pass(output, row, fingerprint, require_production=False):
    require(row.get("fingerprint") == fingerprint,
            "resume fingerprint drift: source/binary/scenario/tool/reference changed; use fresh --out")
    evidence = row.get("evidence")
    require(isinstance(evidence, dict) and evidence, "PASS has no saved evidence")
    attempt = output / row["attempt"]
    for rel, expected in evidence.items():
        path = checked_artifact(output, attempt, output / rel)
        require(sha256(path) == expected, "PASS evidence changed: " + rel)
    report = read_json(attempt / "report.json")
    comparison = read_json(attempt / "comparison.json")
    validate_comparison(comparison, report, row.get("typed_rc"), require_production)


def summarize(summary):
    rows = list(summary["cases"].values())
    summary["counts"] = {status: sum(row.get("status") == status for row in rows)
                         for status in ("PASS", "FAIL", "ERROR", "RUNNING")}
    summary["completed"] = sum(row.get("status") in ("PASS", "FAIL", "ERROR") for row in rows)
    summary["status"] = ("PASS" if len(rows) == summary["expected_cases"] and
                         all(row.get("status") == "PASS" for row in rows) else "INCOMPLETE")
    if any(row.get("status") == "ERROR" for row in rows):
        summary["status"] = "ERROR"
    elif any(row.get("status") == "FAIL" for row in rows):
        summary["status"] = "FAIL"
    summary["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")


def run_gate(args):
    root, output = Path(args.root).resolve(), Path(args.out).resolve()
    validate_output_location(root, output)
    if args.resume:
        require(output.is_dir(), "--resume requires an existing gate output")
        previous = read_json(output / "summary.json")
        require(isinstance(previous, dict) and previous.get("schema") == SCHEMA
                and previous.get("root") == str(root) and isinstance(previous.get("cases"), dict),
                "not an owned gate output for this repository")
    else:
        require(not output.exists(), "output already exists; choose fresh --out or explicitly --resume")
        output.mkdir(parents=True)
    lock = output / ".gate.lock"
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise GateError("output is locked; do not run concurrently (after a crash, inspect/remove .gate.lock manually)")
    os.close(descriptor)
    summary_path = output / "summary.json"
    summary = None
    try:
        if args.resume:
            summary = read_json(summary_path)
            require(isinstance(summary, dict) and summary.get("schema") == SCHEMA
                    and summary.get("root") == str(root), "not an owned gate output for this repository")
        else:
            summary = {"schema": SCHEMA, "root": str(root), "status": "PREFLIGHT",
                       "cases": {}, "expected_cases": 0}
            atomic_json(summary_path, summary)
        fixed = fixed_names(root)
        names = sorted(set(n for arg in (args.scenario or []) for n in arg.split(",") if n))
        if not names:
            require(not args.scenario, "--scenario must not be empty")
            names = fixed
        phases = list(PHASES) if args.phase == "all" else [args.phase]
        typed_exe = (root / args.typed_exe).resolve() if args.typed_exe else None
        config = {"phases": phases, "scenarios": names, "record_unfrozen": args.record_unfrozen,
                  "manifest_count": len(fixed), "typed_exe": str(typed_exe) if typed_exe else None,
                  "require_production": args.require_production}
        if args.resume:
            require(summary.get("config") == config, "resume selection/options differ; use original options or fresh --out")
        summary["config"] = config
        summary["expected_cases"] = len(names) * len(phases)
        plan = build_plan(root, phases, names, fixed, args.record_unfrozen, typed_exe)
        libraries = linked_inputs(root, typed_exe)
        versions = { {"sim": 2, "frames": 3, "snapshots": 4}[p["phase"]]
                     for p in plan if "record" in p["executables"] }
        sources = source_files(root, versions)
        manifest_files = sorted((root / "test_results/typed72-20261108/frames-f7").glob("*.cmp.json"))
        guard_paths = set(sources + manifest_files + libraries)
        for item in plan:
            guard_paths.update([item["source"]] + list(item["executables"].values()))
            if item["reference"] is not None:
                guard_paths.add(item["reference"])
        guard_paths = {path.resolve() for path in guard_paths}
        for path in guard_paths:
            require(path.is_file(), "missing fingerprint input: " + str(path))
        guard = stat_signature(guard_paths)
        common_files = fingerprint_files(sources + manifest_files, root)
        common = digest_json(common_files)
        if args.resume:
            require(summary.get("source_sha256") == common,
                    "resume source/tool/manifest fingerprint drift; use fresh --out")
        summary["source_sha256"] = common
        summary["source_files"] = common_files
        # Hash each actual binary/reference once per invocation, not once per case.
        cached = {}
        for item in plan:
            inputs = [item["source"]] + list(item["executables"].values()) + libraries
            if item["reference"] is not None:
                inputs.append(item["reference"])
            hashes = {}
            for path in inputs:
                path = path.resolve()
                if path not in cached:
                    cached[path] = sha256(path)
                hashes[str(path)] = cached[path]
            item["fingerprint"] = {"sources": common, "inputs": hashes,
                                   "phase": item["phase"], "record_unfrozen": item["recording"]}
            key = item["phase"] + "/" + item["name"]
            old = summary["cases"].get(key)
            if old is not None and old.get("status") == "PASS":
                verify_pass(output, old, item["fingerprint"], args.require_production)
        summary.pop("error", None)
        require(stat_signature(guard_paths) == guard and source_files(root, versions) == sources,
                "input/source changed while fingerprinting; use fresh --out")
        contract = load_sim_contract(root / "build/typed72-match-v1/compare_match.py") if "sim" in phases else None
        for item in plan:
            require(stat_signature(guard_paths) == guard and source_files(root, versions) == sources,
                    "input/source changed during run; stop and choose fresh --out")
            key = item["phase"] + "/" + item["name"]
            old = summary["cases"].get(key)
            if old is not None and old.get("status") == "PASS":
                old["resume_verified"] = True
                print("SKIP (fingerprints verified) " + key, flush=True)
                summarize(summary)
                atomic_json(summary_path, summary)
                continue
            case_dir = output / "cases" / item["phase"] / item["name"]
            case_dir.mkdir(parents=True, exist_ok=True)
            number = 1
            while (case_dir / ("attempt-%04d" % number)).exists():
                number += 1
            attempt = case_dir / ("attempt-%04d" % number)
            attempt.mkdir()
            row = {"status": "RUNNING", "phase": item["phase"], "scenario": item["name"],
                   "attempt": attempt.relative_to(output).as_posix(), "fingerprint": item["fingerprint"],
                   "commands": [], "previous_attempts": []}
            if old:
                row["previous_attempts"] = old.get("previous_attempts", []) + [
                    {k: old.get(k) for k in ("attempt", "status", "error")}]
            summary["cases"][key] = row
            summarize(summary)
            atomic_json(summary_path, summary)
            print("RUN " + key, flush=True)
            started = time.monotonic()
            try:
                execute_case(root, output, item, attempt, row, args.timeout, args.keep_pass_artifacts,
                             contract, args.require_production)
                require(stat_signature(guard_paths) == guard and source_files(root, versions) == sources,
                        "input/source changed during case; evidence is not reusable")
                cleanup_pass(output, attempt, row.pop("cleanup_pending", []))
                row["status"] = "PASS"
            except GateFailure as exc:
                row.update(status="FAIL", error=str(exc))
            except Exception as exc:
                # This is the case boundary: malformed external JSON and OS/process
                # errors must become an explicit ERROR, never a dangling RUNNING.
                row.update(status="ERROR", error="%s: %s" % (type(exc).__name__, exc))
            except KeyboardInterrupt:
                row.update(status="ERROR", error="INTERRUPTED; traces retained")
                raise
            finally:
                row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                summarize(summary)
                atomic_json(summary_path, summary)
            print(row["status"] + " " + key + (": " + row["error"] if "error" in row else ""), flush=True)
        summarize(summary)
        atomic_json(summary_path, summary)
        return 0 if summary["status"] == "PASS" else 1
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(summary, dict) and summary.get("schema") == SCHEMA:
            summary["status"] = "ERROR"
            summary["error"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else str(exc)
            atomic_json(summary_path, summary)
        if isinstance(exc, KeyboardInterrupt):
            return 130
        raise
    finally:
        # The only non-artifact deletion is this exact owned output lock.
        require(lock.resolve().parent == output and not lock.is_symlink(), "unsafe lock path")
        lock.unlink()


def parser():
    value = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    value.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    value.add_argument("--out", required=True, help="new output directory; never an old regression directory")
    value.add_argument("--phase", choices=("sim", "frames", "snapshots", "all"), default="all")
    value.add_argument("--typed-exe", help="override match executable (e.g. production typed72_match_gate.exe)")
    value.add_argument("--require-production", action="store_true",
                       help="require backend_actual=typed72-app-composition-e2 and production_composition=true")
    value.add_argument("--scenario", action="append", help="explicit name(s), repeatable or comma-separated")
    value.add_argument("--record-unfrozen", action="store_true",
                       help="explicitly record non-fixed frame/snapshot scenarios into NEW output only")
    value.add_argument("--resume", action="store_true", help="verify every PASS fingerprint and evidence before skipping")
    value.add_argument("--timeout", type=float, default=1800, help="seconds per subprocess (default: 1800)")
    value.add_argument("--keep-pass-artifacts", action="store_true", help="keep large PASS traces and atlases")
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        require(math.isfinite(args.timeout) and args.timeout > 0, "--timeout must be positive and finite")
        return run_gate(args)
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
