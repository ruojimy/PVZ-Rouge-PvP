#!/usr/bin/env python3
"""Lightweight stdlib-only tests; never launch a game, recorder, compiler or shell.

    python -B tools/typed72/test_regression_gate.py -v

All writes other than these two implementation files are temporary test fixtures.
Every subprocess is mocked, including timeout and nonzero-exit tests.
"""
import contextlib
import copy
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("regression_gate", str(HERE / "regression_gate.py"))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
REPO = HERE.parents[1]


def put(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def put_json(path, value):
    return put(path, json.dumps(value))


def put_lines(path, rows):
    return put(path, "".join(json.dumps(row) + "\n" for row in rows))


def frame(tick, x=1):
    return {"frame": {"tick": tick, "protocol": "native-draw-v1", "tile": 48,
                      "commands": [{"op": "image", "x": x}], "positions": {"hero": [x, 2]}}}


def snapshot(rt, units=None):
    return {"rt": rt, "snapshot": {"tick": rt + 1, "units": [] if units is None else units,
                                    "native_frame": {}, "engine_load": 0.1}}


def sim(tick, number=1):
    return {"t": tick, "rt": tick - 1, "g": {"number": number}, "avatars": {},
            "inp": [], "battle": {"result": None}, "rng": 42, "players": {}}


def final(tick=1):
    return {"tick": tick, "result": None, "log": [{"event": "battle_start", "tick": 0}]}


def report():
    return {"backend_requested": "typed72-integrated", "backend_actual": "typed72-probe-composition-e1",
            "production_composition": False, "failure": "", "fallback_count": 0,
            "typed_step_count": 1, "native_tick_count": 1, "unsupported_operations": [], "unsupported_draws": {}}


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="typed72-gate-test-")
        self.base = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def traces(self, left, right, phase="frames", contract=None):
        a = put_lines(self.base / "reference.jsonl", left)
        b = put_lines(self.base / "typed.jsonl", right)
        return gate.compare_stream(a, b, phase, contract)


class NumberTests(unittest.TestCase):
    def test_inf_never_equals_finite_or_opposite_sign(self):
        for a, b in ((math.inf, 1), (1, math.inf), (-math.inf, 1), (math.inf, -math.inf)):
            with self.subTest(a=a, b=b):
                self.assertFalse(gate.number_equal(a, b))

    def test_matching_nonfinite_classes_are_explicit(self):
        self.assertTrue(gate.number_equal(math.inf, math.inf))
        self.assertTrue(gate.number_equal(-math.inf, -math.inf))
        self.assertFalse(gate.number_equal(math.nan, math.nan))
        self.assertTrue(gate.number_equal(math.nan, math.nan, nan_equal=True))
        self.assertFalse(gate.number_equal(math.nan, math.inf))
        self.assertFalse(gate.number_equal(math.nan, 0))

    def test_relative_tolerance_and_bool_are_not_truthiness(self):
        self.assertTrue(gate.number_equal(1e6, 1e6 + 0.0005))
        self.assertFalse(gate.number_equal(1e6, 1e6 + 0.002))
        self.assertFalse(gate.number_equal(True, 2))


class StreamTests(TemporaryCase):
    def test_valid_frames_are_streamed_and_counted(self):
        value = self.traces([frame(0), frame(8)], [frame(0), frame(8)])
        self.assertTrue(value["identical"])
        self.assertEqual(value["equal_records"], 2)
        self.assertEqual(value["last_typed_tick"], 8)

    def test_empty_trajectories_fail(self):
        for phase in gate.PHASES:
            with self.subTest(phase=phase):
                self.assertFalse(self.traces([], [], phase)["identical"])
        self.assertFalse(self.traces([frame(0)], [])["identical"])

    def test_missing_and_extra_ticks_fail(self):
        for left, right in (([frame(0), frame(1)], [frame(0)]),
                            ([frame(0)], [frame(0), frame(1)]),
                            ([frame(0), frame(1)], [frame(0), frame(2)])):
            with self.subTest(left=len(left), right=len(right)):
                self.assertFalse(self.traces(left, right)["identical"])

    def test_duplicate_ticks_on_either_side_are_rejected(self):
        valid, bad = [frame(0), frame(1)], [frame(0), frame(1), frame(1)]
        for left, right in ((valid, bad), (bad, valid), (bad, bad)):
            with self.assertRaisesRegex(gate.GateError, "duplicate/out-of-order"):
                self.traces(left, right)

    def test_out_of_order_ticks_are_not_sorted(self):
        with self.assertRaisesRegex(gate.GateError, "out-of-order"):
            self.traces([frame(0), frame(2), frame(1)], [frame(0), frame(2), frame(1)])

    def test_frame_position_difference_alone_is_failure(self):
        a, b = frame(0), frame(0)
        b["frame"]["positions"]["hero"][0] = 99
        value = self.traces([a], [b])
        self.assertFalse(value["identical"])
        self.assertIn("positions", str(value["first_difference"]))

    def test_frame_inf_vs_finite_fails(self):
        self.assertFalse(self.traces([frame(0, math.inf)], [frame(0, 1)])["identical"])

    def test_frames_reject_paired_nan(self):
        self.assertFalse(self.traces([frame(0, math.nan)], [frame(0, math.nan)])["identical"])

    def test_snapshots_reject_paired_nan(self):
        row = snapshot(-1, [{"id": "a", "hp": math.nan}])
        self.assertFalse(self.traces([row], [row], "snapshots")["identical"])

    def test_initial_tick_must_exist(self):
        with self.assertRaisesRegex(gate.GateError, "start at tick"):
            self.traces([frame(1)], [frame(1)])

    def test_blank_and_nul_records_and_duplicate_json_keys_fail(self):
        a = put(self.base / "bad.jsonl", "")
        b = put_lines(self.base / "ok.jsonl", [frame(0)])
        for text in ("\n", "\x00\x00", '{"frame":{},"frame":{}}\n'):
            put(a, text)
            with self.subTest(text=repr(text)), self.assertRaises(gate.GateError):
                gate.compare_stream(a, b, "frames")

    def test_snapshot_skips_only_two_documented_fields(self):
        a, b = snapshot(-1), snapshot(-1)
        a["snapshot"]["native_frame"] = {"different": [1, 2]}
        b["snapshot"]["engine_load"] = 9999
        self.assertTrue(self.traces([a], [b], "snapshots")["identical"])
        b["snapshot"]["unknown"] = 1
        self.assertFalse(self.traces([a], [b], "snapshots")["identical"])

    def test_snapshot_extra_and_duplicate_ids_fail(self):
        a = snapshot(-1, [{"id": "a", "x": 1}])
        for units in ([{"id": "a", "x": 1}, {"id": "b", "x": 1}],
                      [{"id": "b", "x": 1}]):
            self.assertFalse(self.traces([a], [snapshot(-1, units)], "snapshots")["identical"])
        dup = snapshot(-1, [{"id": "a"}, {"id": "a"}])
        for left, right in ((a, dup), (dup, a), (dup, dup)):
            with self.assertRaisesRegex(gate.GateError, "duplicate snapshot id"):
                self.traces([left], [right], "snapshots")

    def test_snapshot_list_order_is_preserved(self):
        a = snapshot(-1, [{"id": "a"}, {"id": "b"}])
        b = snapshot(-1, [{"id": "b"}, {"id": "a"}])
        self.assertFalse(self.traces([a], [b], "snapshots")["identical"])

    def test_snapshot_missing_extra_duplicate_and_nonfinite(self):
        for left, right in (([snapshot(-1), snapshot(0)], [snapshot(-1)]),
                            ([snapshot(-1)], [snapshot(-1), snapshot(0)])):
            self.assertFalse(self.traces(left, right, "snapshots")["identical"])
        with self.assertRaisesRegex(gate.GateError, "missing tick"):
            self.traces([snapshot(-1), snapshot(1)], [snapshot(-1), snapshot(1)], "snapshots")
        with self.assertRaisesRegex(gate.GateError, "duplicate"):
            self.traces([snapshot(-1)], [snapshot(-1), snapshot(-1)], "snapshots")
        a = snapshot(-1, [{"id": "a", "hp": math.inf}])
        b = snapshot(-1, [{"id": "a", "hp": 100}])
        self.assertFalse(self.traces([a], [b], "snapshots")["identical"])


class SimulationTests(TemporaryCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = gate.load_sim_contract(REPO / "build/typed72-match-v1/compare_match.py")

    def test_real_legacy_walk_is_patched_recursively(self):
        self.assertFalse(self.traces([sim(0, math.inf)], [sim(0, 1)], "sim", self.contract)["identical"])
        self.assertTrue(self.traces([sim(0, math.inf)], [sim(0, math.inf)], "sim", self.contract)["identical"])
        self.assertTrue(self.traces([sim(0, math.nan)], [sim(0, math.nan)], "sim", self.contract)["identical"])

    def test_sim_missing_fields_and_gaps_fail(self):
        a, b = sim(0), sim(0)
        del b["g"]
        with self.assertRaisesRegex(gate.GateError, "lacks required"):
            self.traces([a], [b], "sim", self.contract)
        b = sim(0)
        b["g"]["extra"] = 1
        self.assertFalse(self.traces([a], [b], "sim", self.contract)["identical"])

    def test_sim_empty_missing_duplicate_extra_ticks_fail(self):
        self.assertFalse(self.traces([], [], "sim", self.contract)["identical"])
        self.assertFalse(self.traces([sim(0)], [sim(0), sim(1)], "sim", self.contract)["identical"])
        for rows in ([sim(0), sim(2)], [sim(0), sim(1), sim(1)]):
            with self.assertRaises(gate.GateError):
                self.traces(rows, rows, "sim", self.contract)

    def comparison(self):
        value = self.traces([sim(0), sim(1)], [sim(0), sim(1)], "sim", self.contract)
        a = put_json(self.base / "a.final.json", final())
        b = put_json(self.base / "b.final.json", final())
        value["final"] = gate.compare_final(a, b, self.contract)
        value["typed_rc"] = 0
        return value

    def test_valid_complete_sim_contract(self):
        gate.validate_comparison(self.comparison(), report(), 0)

    def test_final_tick_is_mandatory_not_just_log_and_result(self):
        value = self.comparison()
        value["final"]["tick_equal"] = False
        with self.assertRaisesRegex(gate.GateFailure, "final tick/log/result"):
            gate.validate_comparison(value, report(), 0)
        value = self.comparison()
        value["final"]["ticks"] = [999, 999]
        with self.assertRaisesRegex(gate.GateFailure, "typed_step_count"):
            gate.validate_comparison(value, report(), 0)

    def test_final_log_result_order_and_nonfinite(self):
        a = put_json(self.base / "a.final.json", final())
        b = put_json(self.base / "b.final.json", final(2))
        self.assertFalse(gate.compare_final(a, b, self.contract)["tick_equal"])
        changed = final()
        changed["result"] = {"winner": "plant"}
        put_json(b, changed)
        self.assertFalse(gate.compare_final(a, b, self.contract)["result_equal"])
        left, right = final(), final()
        left["log"] += [{"event": "move", "x": math.inf}]
        right["log"] += [{"event": "move", "x": 1}]
        put_json(a, left)
        put_json(b, right)
        self.assertFalse(gate.compare_final(a, b, self.contract)["log_equal"])
        right = copy.deepcopy(left)
        right["log"].reverse()
        put_json(b, right)
        self.assertFalse(gate.compare_final(a, b, self.contract)["log_equal"])

    def test_missing_final_or_empty_log_fails(self):
        a = put_json(self.base / "a.final.json", final())
        with self.assertRaisesRegex(gate.GateError, "missing JSON/report"):
            gate.compare_final(a, self.base / "missing", self.contract)
        b = final()
        b["log"] = []
        with self.assertRaisesRegex(gate.GateError, "log empty"):
            gate.compare_final(a, put_json(self.base / "b.final.json", b), self.contract)

    def test_nonempty_matching_counts_and_comparison_rc_required(self):
        for key in ("reference_lines", "typed_lines", "compared", "equal_records", "typed_rc"):
            value = self.comparison()
            value[key] = 9 if key == "typed_rc" else 0
            with self.subTest(key=key), self.assertRaises(gate.GateFailure):
                gate.validate_comparison(value, report(), 0)
        value = self.comparison()
        bad_report = report()
        bad_report["native_tick_count"] = 2
        with self.assertRaisesRegex(gate.GateFailure, "count disagrees"):
            gate.validate_comparison(value, bad_report, 0)


class ReportTests(TemporaryCase):
    def test_nonzero_process_and_report_rc_fail(self):
        with self.assertRaises(gate.GateFailure):
            gate.validate_match_report(report(), 7)
        bad = report()
        bad["rc"] = 7
        with self.assertRaises(gate.GateFailure):
            gate.validate_match_report(bad, 0)

    def test_missing_or_empty_report_is_error(self):
        with self.assertRaisesRegex(gate.GateError, "missing JSON/report"):
            gate.read_json(self.base / "missing.report.json")
        for value in ({}, None, []):
            with self.subTest(value=value), self.assertRaises(gate.GateError):
                gate.validate_match_report(value, 0)

    def test_unsupported_fallback_failure_and_missing_keys_fail(self):
        changes = {"failure": "failed", "fallback_count": 1, "unsupported_operations": ["x"],
                   "unsupported_draws": {"x": 1}, "native_tick_count": -1}
        for key, value in changes.items():
            for remove in (False, True):
                bad = report()
                if remove:
                    del bad[key]
                else:
                    bad[key] = value
                with self.subTest(key=key, remove=remove), self.assertRaises(gate.GateError):
                    gate.validate_match_report(bad, 0)

    def test_backend_identity_and_production_bool_are_required(self):
        for key, value in (("backend_requested", "native"), ("backend_actual", "unknown"),
                           ("production_composition", 1)):
            for remove in (True, False):
                bad = report()
                if remove:
                    del bad[key]
                else:
                    bad[key] = value
                with self.subTest(key=key, remove=remove), self.assertRaises(gate.GateFailure):
                    gate.validate_match_report(bad, 0)

    def test_require_production_rejects_fixture_and_false_claim(self):
        bad = report()
        with self.assertRaisesRegex(gate.GateFailure, "require-production"):
            gate.validate_match_report(bad, 0, require_production=True)
        bad["backend_actual"] = "typed72-app-composition-e2"
        with self.assertRaises(gate.GateFailure):
            gate.validate_match_report(bad, 0, require_production=True)
        bad["production_composition"] = True
        gate.validate_match_report(bad, 0, require_production=True)

    def test_unknown_unsupported_or_fallback_counters_fail(self):
        for key in ("unsupported_widgets", "fallback_calls"):
            bad = report()
            bad[key] = 1
            with self.assertRaises(gate.GateFailure):
                gate.validate_match_report(bad, 0)


class FakeRepository:
    """Tiny disk fixture plus subprocess implementation; no exe is ever started."""
    def __init__(self, base):
        self.root = base / "repo"
        self.output = base / "output"
        self.calls = []
        self.mode = "pass"
        self.root.mkdir()
        for rel in ("src/kernel.cpp", "tools/typed72/generator.py", "build/typed72-match-v1/CMakeLists.txt",
                    "build/typed72-integrated-v44/source/src/kernel.cpp", "CMakeLists.txt"):
            put(self.root / rel, "fixture\n")
        put_json(self.root / "build/typed72-integrated-v44/integration-manifest.json", {"version": 44})
        put(self.root / "build/typed72-match-v1/compare_match.py",
            (REPO / "build/typed72-match-v1/compare_match.py").read_text(encoding="utf-8"))
        for version in (2, 3, 4):
            put(self.root / ("build/typed72-ref-recorder-v%d/CMakeLists.txt" % version), "fixture\n")
            put(self.root / ("build/typed72-ref-recorder-v%d/build/Release/ref72_record.exe" % version), "fake exe")
        for name in ("match72.exe", "cold72_export.exe"):
            put(self.root / "build/typed72-match-v1/build/Release" / name, "fake exe")
        for lib in ("pvzcore.lib", "pvzui.lib", "pvzsnapshot_zlib.lib"):
            put(self.root / "build/Release" / lib, "fake library")
        put(self.root / "build/typed72-integrated-v44/build-zi/Release/pvztyped72.lib", "fake kernel library")
        frozen = self.root / "test_results/typed72-20261108/frames-f7"
        for name in ["basic"] + ["scenario%02d" % i for i in range(57)]:
            put_json(frozen / (name + ".cmp.json"), {})
        self.frame_reference = put_lines(frozen / "basic.frames.jsonl", [frame(0), frame(1)])
        self.snap_reference = put_lines(self.root / "test_results/typed72-20261108/snap-s3/basic.snap.jsonl",
                                        [snapshot(-1), snapshot(0)])
        for name in ("basic", "supp_actions"):
            put_json(self.root / "build/typed72-match-v1/scenarios" / (name + ".json"), {"room_ticks": 1})

    def argv(self, phase="frames", scenario="basic", extra=None):
        return ["--root", str(self.root), "--out", str(self.output), "--phase", phase,
                "--scenario", scenario] + (extra or [])

    def run(self, phase="frames", scenario="basic", extra=None):
        with mock.patch.object(gate.subprocess, "run", side_effect=self.process):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return gate.main(self.argv(phase, scenario, extra))

    def summary(self):
        return gate.read_json(self.output / "summary.json")

    def process(self, command, cwd, env, stdin, stdout, stderr, timeout, check):
        self.calls.append((list(command), dict(env)))
        summary = self.summary()
        assert any(row["status"] == "RUNNING" for row in summary["cases"].values())
        assert env["SDL_VIDEODRIVER"] == env["SDL_AUDIODRIVER"] == "dummy"
        name = Path(command[0]).name
        stdout.write(b"mock process\n")
        if name == "cold72_export.exe":
            put_json(command[2], {})
            put(command[3], "fake atlas")
            put_json(command[3] + ".draw.json", {})
            put_json(command[3] + ".recipes.json", {})
        elif name == "ref72_record.exe":
            if "REF_FRAMES" in env:
                put_lines(env["REF_FRAMES"], [frame(0), frame(1)])
                put(command[2], "unneeded reference trace")
            elif "REF_SNAPSHOTS" in env:
                put_lines(env["REF_SNAPSHOTS"], [snapshot(-1), snapshot(0)])
                put(command[2], "unneeded reference trace")
            else:
                put_lines(command[2], [sim(0), sim(1)])
            put_json(command[2] + ".final.json", final())
        else:
            put_json(command[6], final(2) if self.mode == "final_tick" else final())
            if "MATCH_FRAMES" in env:
                assert env["MATCH_NO_TRACE"] == "1"
                rows = [frame(0), frame(1, 99 if self.mode == "difference" else 1)]
                put_lines(env["MATCH_FRAMES"], rows)
                put(command[4], "")
            elif "MATCH_SNAPSHOTS" in env:
                assert env["MATCH_NO_TRACE"] == "1"
                put_lines(env["MATCH_SNAPSHOTS"], [snapshot(-1), snapshot(0)])
                put(command[4], "")
            else:
                assert "MATCH_NO_TRACE" not in env
                put_lines(command[4], [sim(0), sim(1)])
            if self.mode == "timeout":
                raise subprocess.TimeoutExpired(command, timeout)
            if self.mode != "missing_report":
                value = report()
                if self.mode == "production":
                    value.update(backend_actual="typed72-app-composition-e2", production_composition=True)
                if self.mode == "fallback":
                    value["fallback_count"] = 1
                if self.mode == "nonzero_report":
                    value["rc"] = 3
                put_json(command[5], value)
            if self.mode == "nonzero":
                return subprocess.CompletedProcess(command, 3)
        return subprocess.CompletedProcess(command, 0)


class GateIntegrationTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.fixture = FakeRepository(self.base)

    def test_all_phases_serial_and_frozen_inputs_unchanged(self):
        fixture = self.fixture
        before = [gate.sha256(fixture.frame_reference), gate.sha256(fixture.snap_reference)]
        self.assertEqual(fixture.run("all"), 0)
        self.assertEqual(fixture.summary()["counts"]["PASS"], 3)
        names = [Path(command[0]).name for command, env in fixture.calls]
        self.assertEqual(names, ["cold72_export.exe", "ref72_record.exe", "match72.exe",
                                 "cold72_export.exe", "match72.exe", "cold72_export.exe", "match72.exe"])
        self.assertEqual(before, [gate.sha256(fixture.frame_reference), gate.sha256(fixture.snap_reference)])
        for row in fixture.summary()["cases"].values():
            attempt = fixture.output / row["attempt"]
            self.assertFalse((attempt / "atlas.bin").exists())
            self.assertFalse((attempt / "typed.jsonl").exists())
            self.assertTrue((attempt / "report.json").is_file())

    def test_resume_skips_pass_only_after_rehash_and_json_validation(self):
        fixture = self.fixture
        self.assertEqual(fixture.run(), 0)
        calls = len(fixture.calls)
        self.assertEqual(fixture.run(extra=["--resume"]), 0)
        self.assertEqual(len(fixture.calls), calls)
        self.assertTrue(fixture.summary()["cases"]["frames/basic"]["resume_verified"])

    def test_resume_rejects_source_drift(self):
        fixture = self.fixture
        self.assertEqual(fixture.run(), 0)
        calls = len(fixture.calls)
        put(fixture.root / "src/kernel.cpp", "changed source\n")
        self.assertNotEqual(fixture.run(extra=["--resume"]), 0)
        self.assertEqual(len(fixture.calls), calls)
        self.assertIn("fingerprint drift", fixture.summary()["error"])

    def test_resume_rejects_executable_scenario_reference_and_library_drift(self):
        fixture = self.fixture
        self.assertEqual(fixture.run(), 0)
        paths = [fixture.root / "build/typed72-match-v1/build/Release/match72.exe",
                 fixture.root / "build/typed72-match-v1/scenarios/basic.json",
                 fixture.frame_reference, fixture.root / "build/Release/pvzcore.lib"]
        for path in paths:
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            calls = len(fixture.calls)
            with self.subTest(path=path.name):
                self.assertNotEqual(fixture.run(extra=["--resume"]), 0)
                self.assertEqual(len(fixture.calls), calls)
            path.write_bytes(original)
        self.assertEqual(fixture.run(extra=["--resume"]), 0)

    def test_resume_rejects_corrupt_pass_report_and_comparison(self):
        fixture = self.fixture
        self.assertEqual(fixture.run(), 0)
        attempt = fixture.output / fixture.summary()["cases"]["frames/basic"]["attempt"]
        for name in ("report.json", "comparison.json"):
            path = attempt / name
            original = path.read_bytes()
            path.write_bytes(b"\x00" * len(original))
            calls = len(fixture.calls)
            with self.subTest(name=name):
                self.assertNotEqual(fixture.run(extra=["--resume"]), 0)
                self.assertEqual(len(fixture.calls), calls)
            path.write_bytes(original)

    def test_keep_pass_and_no_overwrite_existing_output(self):
        fixture = self.fixture
        self.assertEqual(fixture.run(extra=["--keep-pass-artifacts"]), 0)
        row = fixture.summary()["cases"]["frames/basic"]
        self.assertTrue((fixture.output / row["attempt"] / "atlas.bin").is_file())
        before = (fixture.output / "summary.json").read_bytes()
        self.assertNotEqual(fixture.run(), 0)
        self.assertEqual((fixture.output / "summary.json").read_bytes(), before)

    def test_failures_retain_traces_and_resume_uses_new_attempt(self):
        fixture = self.fixture
        fixture.mode = "difference"
        self.assertNotEqual(fixture.run(), 0)
        row = fixture.summary()["cases"]["frames/basic"]
        first = fixture.output / row["attempt"]
        self.assertEqual(row["status"], "FAIL")
        self.assertTrue((first / "typed.frames.jsonl").is_file())
        self.assertTrue((first / "atlas.bin").is_file())
        fixture.mode = "pass"
        self.assertEqual(fixture.run(extra=["--resume"]), 0)
        later = fixture.summary()["cases"]["frames/basic"]
        self.assertNotEqual(row["attempt"], later["attempt"])
        self.assertTrue((first / "typed.frames.jsonl").is_file())
        self.assertEqual(later["previous_attempts"][0]["status"], "FAIL")

    def test_input_drift_during_case_is_error_and_keeps_traces(self):
        fixture = self.fixture
        original = fixture.process

        def changing(*args, **kwargs):
            result = original(*args, **kwargs)
            if Path(args[0][0]).name == "match72.exe":
                put(fixture.root / "src/kernel.cpp", "changed while running")
            return result

        fixture.process = changing
        self.assertNotEqual(fixture.run(), 0)
        row = fixture.summary()["cases"]["frames/basic"]
        self.assertEqual(row["status"], "ERROR")
        self.assertIn("changed during case", row["error"])
        self.assertTrue((fixture.output / row["attempt"] / "typed.frames.jsonl").is_file())

    def test_resume_does_not_modify_an_unowned_old_directory(self):
        fixture = self.fixture
        old = put_json(fixture.output / "summary.json", {"old_results": True})
        before = old.read_bytes()
        self.assertNotEqual(fixture.run(extra=["--resume"]), 0)
        self.assertEqual(old.read_bytes(), before)
        self.assertFalse((fixture.output / ".gate.lock").exists())
        self.assertFalse(fixture.calls)

    def test_timeout_is_explicit_error_and_keeps_artifacts(self):
        fixture = self.fixture
        fixture.mode = "timeout"
        self.assertNotEqual(fixture.run(), 0)
        row = fixture.summary()["cases"]["frames/basic"]
        self.assertEqual(row["status"], "ERROR")
        self.assertIn("TIMEOUT", row["error"])
        self.assertEqual(fixture.summary()["status"], "ERROR")
        self.assertEqual(row["commands"][-1]["status"], "ERROR")
        self.assertTrue((fixture.output / row["attempt"] / "typed.frames.jsonl").is_file())

    def test_process_missing_and_nonzero_report_all_fail(self):
        fixture = self.fixture
        for mode in ("nonzero", "missing_report", "fallback", "nonzero_report"):
            fixture.output = self.base / ("out-" + mode)
            fixture.mode = mode
            with self.subTest(mode=mode):
                self.assertNotEqual(fixture.run(), 0)
                row = fixture.summary()["cases"]["frames/basic"]
                self.assertIn(row["status"], ("FAIL", "ERROR"))
                self.assertTrue((fixture.output / row["attempt"] / "typed.frames.jsonl").is_file())

    def test_final_tick_mismatch_fails_sim_and_retains_traces(self):
        fixture = self.fixture
        fixture.mode = "final_tick"
        self.assertNotEqual(fixture.run("sim"), 0)
        row = fixture.summary()["cases"]["sim/basic"]
        self.assertEqual(row["status"], "FAIL")
        self.assertTrue((fixture.output / row["attempt"] / "reference.jsonl").exists())
        value = gate.read_json(fixture.output / row["attempt"] / "comparison.json")
        self.assertFalse(value["final"]["tick_equal"])

    def test_manifest_requires_exactly_58(self):
        fixture = self.fixture
        extra = fixture.frame_reference.parent / "extra.cmp.json"
        put_json(extra, {})
        self.assertNotEqual(fixture.run(), 0)
        self.assertFalse(fixture.calls)
        self.assertIn("exactly 58", fixture.summary()["error"])

    def test_missing_fixed_reference_never_rerecorded_even_with_flag(self):
        fixture = self.fixture
        # Empty fixture stands in for a missing/corrupt frozen trace, without
        # deleting any project path or any production reference.
        put(fixture.frame_reference, "")
        self.assertNotEqual(fixture.run(extra=["--record-unfrozen"]), 0)
        self.assertFalse(fixture.calls)
        self.assertIn("will NOT re-record", fixture.summary()["error"])

    def test_unfrozen_requires_explicit_opt_in_and_uses_v3_v4(self):
        fixture = self.fixture
        self.assertNotEqual(fixture.run("frames", "supp_actions"), 0)
        self.assertFalse(fixture.calls)
        fixture.output = self.base / "unfrozen-all"
        self.assertEqual(fixture.run("all", "supp_actions", ["--record-unfrozen"]), 0)
        recorders = [command[0] for command, env in fixture.calls if Path(command[0]).name == "ref72_record.exe"]
        self.assertEqual(len(recorders), 3)
        for version, executable in zip((2, 3, 4), recorders):
            self.assertIn("typed72-ref-recorder-v%d" % version, executable)

    def test_sim_clears_inherited_trace_control_environment(self):
        with mock.patch.dict(os.environ, {"MATCH_NO_TRACE": "1", "REF_FRAMES": "do-not-write", "MATCH_FRAMES": "do-not-write"}):
            self.assertEqual(self.fixture.run("sim"), 0)
        for command, env in self.fixture.calls:
            self.assertNotIn("REF_FRAMES", env)
            self.assertNotIn("MATCH_NO_TRACE", env)
            self.assertNotIn("MATCH_FRAMES", env)

    def test_typed_exe_override_is_executed_and_fingerprinted(self):
        fixture = self.fixture
        executable = put(fixture.root / "build/app-typed72-v2/Release/typed72_match_gate.exe", "production mock")
        kernel = put(executable.parent / "pvztyped72kernel.lib", "production library")
        extra = ["--typed-exe", str(executable)]
        self.assertEqual(fixture.run(extra=extra), 0)
        self.assertEqual(fixture.calls[-1][0][0], str(executable))
        row = fixture.summary()["cases"]["frames/basic"]
        self.assertIn(str(executable), row["fingerprint"]["inputs"])
        self.assertIn(str(kernel), row["fingerprint"]["inputs"])
        put(executable, "changed production mock")
        self.assertNotEqual(fixture.run(extra=extra + ["--resume"]), 0)

    def test_require_production_cli_and_case_backend_evidence(self):
        fixture = self.fixture
        self.assertNotEqual(fixture.run(extra=["--require-production"]), 0)
        fixture.output = self.base / "production"
        fixture.mode = "production"
        self.assertEqual(fixture.run(extra=["--require-production"]), 0)
        row = fixture.summary()["cases"]["frames/basic"]
        self.assertEqual(row["backend_actual"], "typed72-app-composition-e2")
        self.assertIs(row["production_composition"], True)
        self.assertEqual(fixture.run(extra=["--require-production", "--resume"]), 0)

    def test_hash_roots_exclude_history_but_include_generated_driver_tools(self):
        fixture = self.fixture
        for rel in ("build/typed72-match-v1/build/history/huge.cpp", "test_results/old/huge.cpp",
                    "build/typed72-integrated-v43/source/history.cpp", "tools/typed72/drafts/a.cpp.bak"):
            put(fixture.root / rel, "not an active input")
        included = ["src/sim/typed72_app/composition/match_probe.cpp", "tools/typed72/generate.py",
                    "build/typed72-match-v1/probes/plants_probe.cpp",
                    "build/typed72-integrated-v44/source/src/typed/generated.cpp"]
        for rel in included:
            put(fixture.root / rel, "active input")
        files = [p.relative_to(fixture.root).as_posix() for p in gate.source_files(fixture.root, {2})]
        self.assertTrue(all(rel in files for rel in included))
        self.assertFalse(any("huge" in rel or "v43" in rel or ".bak" in rel for rel in files))
        self.assertIn("build/typed72-ref-recorder-v2/CMakeLists.txt", files)

    def test_safe_cleanup_rejects_external_path(self):
        output = self.base / "owned"
        attempt = output / "cases/a/attempt-0001"
        owned = put(attempt / "atlas.bin", "owned")
        outside = put(self.base / "frozen-reference.jsonl", "do not touch")
        with self.assertRaisesRegex(gate.GateError, "unsafe artifact"):
            gate.cleanup_pass(output, attempt, [outside])
        self.assertTrue(outside.exists())
        gate.cleanup_pass(output, attempt, [owned])
        self.assertFalse(owned.exists())

    def test_output_cannot_overlap_inputs(self):
        fixture = self.fixture
        for rel in ("src/new", "build/new", "test_results/typed72-20261108/frames-f7/new"):
            with self.subTest(rel=rel), self.assertRaises(gate.GateError):
                gate.validate_output_location(fixture.root, fixture.root / rel)


if __name__ == "__main__":
    unittest.main()
