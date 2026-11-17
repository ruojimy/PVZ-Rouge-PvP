"""Check the production-library material probes; never rewrites the original audit."""
import argparse
import collections
import json
from pathlib import Path


def verify(root):
    read = lambda name: json.loads((root / name).read_text(encoding="utf-8-sig"))
    failures, checks = [], []

    def check(name, passed, **evidence):
        row = dict(name=name, passed=bool(passed), **evidence)
        checks.append(row)
        if not passed:
            failures.append(row)

    batches = {n: read(n + ".json") for n in
               ["matrix", "projectile", "projectile-no-cold", "chili-survivors"]}
    for name, batch in batches.items():
        check(name + "/completed", batch["errors"] == 0 and all(s["completed"] for s in batch["scenarios"]),
              scenarios=len(batch["scenarios"]))
        check(name + "/cache-assertions", not batch["assertion_failures"], errors=batch["assertion_failures"])
        errors = [dict(name=s["name"], frames=len(s["native_view_errors"])) for s in batch["scenarios"] if s.get("native_view_errors")]
        check(name + "/native-view", not errors, errors=errors)
    rows = {s["name"]: s for s in batches["matrix"]["scenarios"]}
    count = lambda frame, tag=None: collections.Counter(frame["all"] if tag is None else frame["tags"].get(tag, {}))
    groups = sorted({n.rsplit("/", 1)[0] for n in rows if n.startswith(("pair/", "alpha/", "status/"))})
    for group in groups:
        members = {order: rows[group + "/" + order] for order in ["A", "B", "AB", "BA"]}
        if not all(s["completed"] for s in members.values()):
            check(group, False, reason="incomplete scenario")
            continue
        # Lantern phototherapy is an intended interaction, verified by the audit.
        if group == "pair/普通僵尸+路灯花僵尸":
            continue
        whole, attribution = [], []
        for tick in range(6):
            expected = count(members["A"]["timeline"][tick]) + count(members["B"]["timeline"][tick])
            expected.subtract(count(rows["empty-control"]["timeline"][tick]))
            for order in ["AB", "BA"]:
                if +expected != count(members[order]["timeline"][tick]):
                    whole.append(dict(order=order, tick=tick))
                for tag in ["A", "B"]:
                    if count(members[tag]["timeline"][tick], tag) != count(members[order]["timeline"][tick], tag):
                        attribution.append(dict(order=order, tick=tick, tag=tag))
        check(group + "/materials-and-alpha", not whole, differences=whole)
        if group.startswith("pair/"):
            check(group + "/attribution", not attribution, differences=attribution)

    atlas = batches["matrix"]["atlas"]
    aliases = atlas["alias_restore_checks"]
    check("all-alias-restores", len(aliases) == 180 and all(c[k] for c in aliases for k in
          ["single_alias_restored", "repeated_alias_restored", "tint_then_alias_restored"]), mappings=len(aliases))
    heads = atlas["plant_zombie_head_cache"]
    check("all-head-caches", len(heads) == 13 and all(c[k] for c in heads for k in
          ["left_changes_under_poison", "right_has_poison", "healthy_left_restored"]), types=len(heads))
    check("carrier-cache", atlas["carrier_cache"]["isolated"])
    for name in ["projectile", "projectile-no-cold"]:
        for scene in batches[name]["scenarios"]:
            palettes = [f["tags"].get("source", {}) for f in scene["timeline"]]
            frames = sum(any(k in p for k in ["world:火豆", "world:蓝火豆"]) for p in palettes)
            bad = sum(any("原始火豆" in k or "原始蓝火豆" in k or "寒冰-火" in k for k in p) for p in palettes)
            check(name + "/" + scene["name"], frames > 0 and bad == 0, fire_frames=frames, foreign_frames=bad)
    flame_keys = {"world:" + k for k in ["火1.1", "火1.2", "火1.3", "火2", "火3"]}
    flame_scenes = [s for s in rows.values() if s["name"].startswith("flame/plant:")]
    flame_scenes += batches["chili-survivors"]["scenarios"]
    for scene in flame_scenes:
        palettes = [f["tags"].get("fire", {}) for f in scene["timeline"]]
        red = sum(bool(flame_keys.intersection(p)) for p in palettes)
        cold = sum(any(k.startswith("world:寒冰-火") for k in p) for p in palettes)
        check(scene["name"], red == 19 and cold == 0, red_frames=red, foreign_cold_frames=cold)
    scope = read("workshop-scope.json")
    check("workshop/full-key-isolation", scope["errors"] == 0 and len(scope["tests"]) == 328 and
          all(not c["lookup_returns_source_override"] for c in scope["tests"]), directions=len(scope["tests"]))
    for name in ["workshop", "hero-grave"]:
        file = (name + "-final" if (root / (name + "-final/summary.json")).exists() else name) + "/summary.json"
        suite = read(file)
        check(name + "/existing-suite", suite["passed"] and all(c["passed"] for c in suite["checks"]), checks=len(suite["checks"]), evidence=file)
    pixels = read("pixels.json")
    check("actual-rendered-pixels", pixels["passed"], checks=len(pixels["checks"]), errors=[c for c in pixels["checks"] if not c["passed"]])
    hooks = read("hook-regeneration.json")
    check("hooks-survive-ui-regeneration", hooks["passed"], checks=hooks["checks"])
    # These are sampled native health/status/projectile observations, not a
    # claim of exhaustive combat or cross-machine replay acceptance.
    baseline = root.with_name("material-isolation-20261116")
    old_read = lambda name: json.loads((baseline / (name + ".json")).read_text(encoding="utf-8-sig"))
    original = {s["name"]: s for name in ["matrix", "supplement"] for s in old_read(name)["scenarios"]}
    differences, compared, nonempty = [], 0, 0
    for name, batch in batches.items():
        before = original if name == "matrix" else {s["name"]: s for s in old_read(name)["scenarios"]}
        after = {s["name"]: s for s in batch["scenarios"]}
        for key, scene in before.items():
            if key not in after:
                continue
            unavailable = {s["step"] for s in scene.get("native_view_errors", [])}
            for i, frame in enumerate(scene["timeline"]):
                if frame["step"] in unavailable:
                    continue
                for field in ["statuses", "shots"]:
                    if field not in frame:
                        continue
                    compared += 1
                    nonempty += bool(frame[field])
                    if i >= len(after[key]["timeline"]) or frame[field] != after[key]["timeline"][i][field]:
                        differences.append(dict(batch=name, scene=key, step=frame["step"], field=field))
    comparison = dict(passed=not differences, compared_fields=compared, nonempty_fields=nonempty, differences=differences)
    (root / "simulation-observation-comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    check("native-observations-match-pre-fix", not differences and nonempty > 0, **{k: v for k, v in comparison.items() if k != "passed"})
    return dict(passed=not failures, scenarios=sum(len(b["scenarios"]) for b in batches.values()),
                checks=checks, failures=failures, exclusions=["4 invalid direct spawns from original audit", "intended lantern phototherapy interaction"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    result = verify(args.results)
    (args.results / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(passed=result["passed"], scenarios=result["scenarios"], checks=len(result["checks"]), failures=result["failures"]), ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
