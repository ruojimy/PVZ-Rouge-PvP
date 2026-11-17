"""Derive architecture evidence from existing runs; reproduce duplicate-view interpolation.

No game binary is started or changed. This does not measure device input latency.
Run from any directory: python tools/pvp744_architecture_probe.py
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "test_results/pvp744/scheduler-20261116"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interpolation_reproduction():
    source = ROOT / "tools/pvp72_sources/presentation.py"
    cls = runpy.run_path(str(source))["GuestPresentation"]
    now = [10.0]
    presentation = cls(clock=lambda: now[0])

    def frame(time, x):
        return {
            "phase": "battle", "terrain_hash": "fixed", "pacing": {"slow": True},
            "map": {"width": 960, "tile_size": 48},
            "battle": {
                "time": time, "players": {}, "units": [{"id": "u", "x": x, "y": 0}],
                "native_frame": {"positions": {"u": [x, 0]}},
            },
        }

    presentation.accept(frame(0, 0))
    now[0] = 10.02
    current = frame(1 / 30, 10)
    presentation.accept(current)
    now[0] = 10.03
    before = presentation.sample(current)["battle"]["units"][0]["x"]
    duration = presentation.duration
    duplicate = frame(1 / 30, 10)
    presentation.accept(duplicate)
    after = presentation.sample(duplicate)["battle"]["units"][0]["x"]
    reproduced = abs(before - 3) < 1e-8 and after == 10 and presentation.duration == 0
    return {
        "source": str(source.relative_to(ROOT)), "sha256": digest(source),
        "scenario": "Same authority time and pose, new outer view object, unchanged wall clock at duplicate accept",
        "shown_x_before": before, "shown_x_after": after,
        "duration_before_seconds": duration, "duration_after_seconds": presentation.duration,
        "duplicate_cancels_interpolation": reproduced,
        "scope": "Owning Python presentation implementation with fake clock; generated C++ separately inspected; not a game/physical-input run",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "test_results/pvp744/architecture-20261116/evidence.json")
    args = parser.parse_args()
    cases = {}
    inputs = {}
    for name in ("view-ab/grabber-adaptive", "view-ab/grabber-view", "wall-ab/grabber-legacy", "wall-ab/grabber-adaptive", "profile/grabber-adaptive"):
        path = RUNS / name / "report.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        inputs[str(path.relative_to(ROOT))] = digest(path)
        phases = data["frame_phases_ms"]
        advanced = phases["refresh_advanced"]["samples"]
        cases[name] = {
            "wall_seconds": data["wall_seconds"], "native_ticks": data["native_ticks"],
            "presentation": data["presentation"], "simulation_wall_ratio": data["simulation_wall_ratio"],
            "phases": {key: phases[key] for key in (
                "frame_work", "authority_sim", "authority_room_overhead", "refresh_advanced",
                "refresh_idle", "render", "present", "frame_interval_actual")},
            "advanced_fraction_of_service_iterations": advanced / phases["frame_work"]["samples"],
            "session_ms_per_advanced_iteration": phases["authority_sim"]["total"] / advanced,
            "session_plus_refresh_mean_per_advanced_iteration_ms": (
                phases["authority_sim"]["total"] + phases["refresh_advanced"]["total"]) / advanced,
            "session_ms_per_native_tick": phases["authority_sim"]["total"] / data["native_ticks"],
            "same_work_state_hash": data["final_state_sha256"],
            "same_work_rng_hash": data["final_rng_sha256"],
        }
        if name.startswith("profile/"):
            profile = data["backend_audit"]["performance"]["function_profile"]
            wanted = (
                "NativeTick::run", "NativeTick::effects_and_draw_plants", "NativeTick::effects::draw_plants",
                "NativeTick::plant_actions", "NativeTracking::begin", "TypedBattle::frame_projection",
                "MatchProbe::snapshot_json", "WorldView::render", "DrawReplay::render")
            cases[name]["inclusive_functions_do_not_sum"] = {key: profile[key] for key in wanted}
            draw = profile["NativeTick::effects::draw_plants"]["total_ms"]
            work = phases["frame_work"]["total"]
            cases[name]["draw_plants_share_of_effects"] = draw / profile["NativeTick::effects_and_draw_plants"]["total_ms"]
            cases[name]["draw_plants_share_of_native_tick"] = draw / profile["NativeTick::run"]["total_ms"]
            cases[name]["draw_plants_share_of_frame_work"] = draw / work
            cases[name]["hypothetical_work_speedup_if_draw_plants_free"] = work / (work - draw)
    sources = (
        "src/ui/gen/pm_app.cpp", "tools/pvp72_sources/app.py", "src/ui/gen/pm_presentation.cpp",
        "tools/pvp72_sources/presentation.py", "src/ui/hand/pressure_pacing.cpp",
        "src/sim/typed72_app/typed_battle.cpp", "src/sim/typed72_app/frame_projection.h",
        "src/sim/typed72_app/session.cpp", "src/sim/typed72_app/session.h",
        "build/typed72-match-v1/snapshot_layer.inc", "build/typed72-match-v1/frame_layer.inc",
        "build/typed72-integrated-v44/source/src/sim/typed/room_scheduler.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_tick.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_plant_draw.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_content_draw.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/content_plants70.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_tracking.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_art.h",
        "build/typed72-integrated-v44/source/src/sim/typed/native_art.cpp",
        "build/typed72-integrated-v44/source/src/sim/typed/native_frame.cpp",
        "tools/pvp72_sources/world_view.py", "src/pg/system.cpp", "src/core/gil.h",
        "src/sim/pvp/hand/snapshot_pack.cpp",
    )
    reproduction = interpolation_reproduction()
    evidence = {
        "format": "pvp744-architecture-evidence-v1", "date": "2026-11-16",
        "scope": "Existing PC diagnostic runs, current owning sources and one isolated presentation reproduction. No new Android, full game regression or human acceptance.",
        "timing_notes": [
            "authority_sim measures Session::step wall duration, including draw recipe work and room publication; not rules-only CPU time.",
            "Function timings are inclusive; do not add parents and children or sum separate p95 values.",
            "Per-advanced costs derive from this fixture's complete-window totals; not a general per-step latency bound.",
            "Hypothetical free-work speedup is an accounting bound at fixed work, not measured FPS or an implementation forecast.",
            "Fixed-scale and adaptive wall-time cases have different workloads; do not treat their differences as a controlled optimization comparison.",
        ],
        "input_reports_sha256": inputs,
        "source_sha256": {name: digest(ROOT / name) for name in sources},
        "cases": cases, "interpolation_reproduction": reproduction,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(args.out.resolve()), "interpolation_issue_reproduced": reproduction["duplicate_cancels_interpolation"], "reports": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
