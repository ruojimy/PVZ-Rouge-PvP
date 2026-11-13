"""Isolated A/B runner for the production Application refresh regression executable.

The C++ fixture uses real Application/Room/typed simulation with a queued transport,
so this verifies the application integration without claiming WAN/VPN coverage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    executable = args.executable.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    runs = []
    for name, enabled in (("baseline", "0"), ("optimized", "1")):
        env = os.environ.copy()
        env.update(PVP742_INPUT_REFRESH=enabled, PVP741_PROFILE="1",
                   PVP_NET_PACK_WORKER="inline", SDL_VIDEODRIVER="dummy",
                   SDL_AUDIODRIVER="dummy", PVP_USERDATA=str(output / (name + "-userdata")))
        report_path = output / (name + ".json")
        with (output / (name + ".stdout.log")).open("wb") as stdout, \
                (output / (name + ".stderr.log")).open("wb") as stderr:
            result = subprocess.run([str(executable), str(report_path)], cwd=root,
                                    env=env, stdout=stdout, stderr=stderr, timeout=300)
        runs.append({"name": name, "exit_code": result.returncode})
        if report_path.exists():
            reports[name] = json.loads(report_path.read_text(encoding="utf-8"))
        if result.returncode:
            print((output / (name + ".stderr.log")).read_text(encoding="utf-8", errors="replace"))
    comparison = {"runs": runs, "passed": False,
                  "scope": "production Application/Room/typed battle; queued transport events; no real WAN test"}
    if len(reports) == 2:
        def by_name(name):
            return {row["name"]: row for row in reports[name]["checks"]}
        before, after = by_name("baseline"), by_name("optimized")
        equal = {}
        for case, field in (("remote_jump_edges_and_non_move_input_order", "battle"),
                            ("remote_jump_edges_and_non_move_input_order", "accepted_order"),
                            ("coop_knockdown_heartbeats_and_real_revival", "players")):
            key = case + "." + field
            equal[key] = (before[case].get("evidence", {}).get(field) ==
                          after[case].get("evidence", {}).get(field) and
                          field in before[case].get("evidence", {}))
        comparison["deterministic_equal"] = equal
        comparison["burst_measurements"] = []
        key = "production_application_remote_neutral_bursts"
        if before[key]["passed"] and after[key]["passed"]:
            for a, b in zip(before[key]["evidence"], after[key]["evidence"]):
                comparison["burst_measurements"].append({
                    "commands": a["commands"], "before_refreshes": a["refreshes"],
                    "after_refreshes": b["refreshes"], "before_refresh_ms": a["refresh_ms"],
                    "after_refresh_ms": b["refresh_ms"], "before_frame_ms": a["frame_ms"],
                    "after_frame_ms": b["frame_ms"],
                    "before_typed_frame_projections": a["typed_frame_projections"],
                    "after_typed_frame_projections": b["typed_frame_projections"],
                    "ack_seq": b["ack_seq"]})
        comparison["passed"] = (all(run["exit_code"] == 0 for run in runs) and
                                all(equal.values()) and
                                all(report["failures"] == 0 for report in reports.values()))
        dense = "dense_plane_tentacle_view_remote_burst"
        if before[dense]["passed"] and after[dense]["passed"]:
            comparison["dense_view_measurement"] = {
                "before": before[dense]["evidence"], "after": after[dense]["evidence"],
                "requested_spawns": 300,
                "scope": "{} public actors after 300 primary spawns, 25 neutral heartbeat burst, zero simulation advancement".format(after[dense]["evidence"]["units"])}
    comparison["exe_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    (output / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0 if comparison["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
