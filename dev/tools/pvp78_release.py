"""Stage, audit and promote the six-mode PvP78 release."""
import argparse
import os
import sys
from pathlib import Path

import pvp77_release as base

r = base.release
source = base.previous.SOURCE.replace("PvP76", "PvP78")
source = source.replace("'MANIFEST-PvP78.json','STAGING_STATUS.json'", "'MANIFEST-PvP76.json','MANIFEST-PvP77.json','MANIFEST-PvP78.json','STAGING_STATUS.json'")
source = source.replace("本地演练 → 测试模式 可体验三个 Boss 和作弊器；合作第 8/16/24 关新增 Boss。", "主界面下方的闯关模式可进入三种合作与三种单人挑战。")
start = source.index("    cases = ", source.index("def smoke():"))
end = source.index("    results = []", start)
source = source[:start] + "    cases = [('pvp76r3_audit','pvp78')]\n" + source[end:]
source = source.replace("timeout=300, creationflags", "timeout=1800, creationflags")
extra_evidence = [
    "atlas-comparison.json", "render-profile/comparison.json", "workshop/summary.json",
    "legacy-mode-isolation/results.json", "legacy-follow-orders/results.json", "android/interaction.json", "android/performance.json",
    "android/78-selector.png",
    "android/78-ime-open.png", "android/78-ime-after-hide.png",
    "lan-final-lottery/host.log", "lan-final-lottery/guest.log",
    "lan-final-izombie/host.log", "lan-final-izombie/guest.log",
]
r4 = "--r4" in sys.argv
r3 = "--r3" in sys.argv or r4
r2 = "--r2" in sys.argv or r3
if r2:
    extra_evidence = [
        "r2/2v2-map-comparison.png", "r2/android/interaction.json", "r2/android/78-shop.png",
        "r2/android/78-coop-options.png", "r2/android/78-reward.png",
        "r2/lan-final-lottery/host.log", "r2/lan-final-lottery/guest.log",
        "r2/lan-final-izombie/host.log", "r2/lan-final-izombie/guest.log",
    ]
if r4:
    extra_evidence=["r4/android/interaction.json","r4/android/verification.jpg","r4/selected-draft-verification.json"]
elif r3:
    extra_evidence=[p.replace("r2/","r3/") for p in extra_evidence]
source = source.replace("    entries['README.md']=", "    for rel in " + repr(extra_evidence) + ":\n        path=ROOT/'test_results/pvp78'/rel\n        if path.is_file(): entries[path.relative_to(ROOT).as_posix()]=path\n    entries['README.md']=")
exec(compile(source, r.__file__, "exec"), r.__dict__)
r.VERSION = "1.6.0.78-typed.20261124-r1"
r.REV, r.PREVIOUS_REV = "pvp78-r1", "pvp77-r4"
r.CODE, r.NATIVE_RUN = 1124083, "pvp78d-20261124-r1"
r.STAGE = base.ROOT / "dist/PvZ-PvP-Native-20261124-pvp78-r1"
r.OUT = base.ROOT / "test_results/pvp78/release"
r.APK_DIR = base.ROOT / "dist/apk-pvp78-r1-20261124"
if r2:
    r.VERSION = "1.6.0.78-typed.20261125-r2"
    r.REV, r.PREVIOUS_REV = "pvp78-r2", "pvp78-r1"
    r.CODE, r.NATIVE_RUN = 1125084, "pvp78r2-20261125-b"
    r.STAGE = base.ROOT / "dist/PvZ-PvP-Native-20261125-pvp78-r2"
    r.OUT = base.ROOT / "test_results/pvp78/r2/release"
    r.APK_DIR = base.ROOT / "dist/apk-pvp78-r2-20261125"
if r3:
    r.VERSION = "1.6.0.78-typed.20261125-r3"
    r.REV, r.PREVIOUS_REV = "pvp78-r3", "pvp78-r1"
    r.CODE, r.NATIVE_RUN = 1125085, "pvp78r3-20261125-c"
    r.STAGE = base.ROOT / "dist/PvZ-PvP-Native-20261125-pvp78-r3"
    r.OUT = base.ROOT / "test_results/pvp78/r3/release"
    r.APK_DIR = base.ROOT / "dist/apk-pvp78-r3-20261125"
if r4:
    r.VERSION = "1.6.0.78-typed.20261125-r4"
    r.REV, r.PREVIOUS_REV = "pvp78-r4", "pvp78-r3"
    r.CODE, r.NATIVE_RUN = 1125086, "pvp78r4-ai-20261125-b"
    r.STAGE = base.ROOT / "dist/PvZ-PvP-Native-20261125-pvp78-r4"
    r.OUT = base.ROOT / "test_results/pvp78/r4/release"
    r.APK_DIR = base.ROOT / "dist/apk-pvp78-r4-20261125"
r.helpers.VERSION, r.helpers.OUT, r.helpers.STAGE = r.VERSION, r.OUT, r.STAGE
base.previous.release = r


def regression_status():
    verification = r.read(r.OUT / "packaged-feature-verification.json")
    case, = verification["cases"]
    report = r.read(Path(case["report"]))
    group, = report["checks"]
    if r4:
        assert group["name"]=="pvp78ai" and group["passed"] and not report["failures"]
        rows={e["id"]:e for e in group["evidence"]}
        assert set(rows)=={"ai78.native_drafts","ai78.advice","ai78.test_mode","ai78.team_combat"} and all(e["passed"] for e in rows.values())
        assert verification["passed"] and r.read(r.OUT/"pc-smoke-verification.json")["passed"]
        assert case["executable_sha256"]==r.sha(r.BUILD/"pvp76r3_audit.exe")
        assert r.read(r.OUT/"stage.json")["exe_sha256"]==r.sha(r.STAGE/"PvZPvPNative.exe")==r.sha(r.BUILD/"PvZPvPNative.exe")
        model=r.STAGE/"extract/data/pvp/ai/ranked-fast-heads.json"
        reference=r.read(r.OUT.parent/"selected-draft-verification.json")
        assert reference["model_sha256"]==r.sha(model) and reference["cards"]==rows["ai78.native_drafts"]["ranked"]
        mobile=r.read(r.OUT.parent/"android/interaction.json")
        apk=r.read(r.OUT/"android-package-verification.json")
        assert mobile["passed"] and apk["passed"] and apk["sha256"]==mobile["apk_sha256"]
        assert apk["all_assets"]["extract/data/pvp/ai/ranked-fast-heads.json"]==reference["model_sha256"]==mobile["installed_model_sha256"]
        prior=r.read(r.OUT/"promotion-before.json")["previous"].get("full_regression_report")
        return dict(targeted_verification_passed=True,targeted_report=case["report"],android_emulator_interaction_verified=True,
                    full_regression_rerun=False,full_regression_passed=None,previous_full_regression_report=prior,full_regression_report=prior)
    assert group["name"] == "pvp78" and group["passed"] and not report["failures"]
    expected = {"menu_and_difficulty", "coop.lottery", "coop.izombie", "keyboard",
                "trophies", "mode_boundaries", "commander_targeting", "defender_density",
                "waves", "health"}
    if r3: expected.add("map_cycles")
    evidence = group["evidence"]
    assert {row["id"] for row in evidence} == {"campaign78." + name for name in expected}
    assert len(evidence) == len(expected) and all(row["passed"] for row in evidence)
    assert verification["passed"] and r.read(r.OUT / "pc-smoke-verification.json")["passed"]
    assert r.sha(r.BUILD / "pvp76r3_audit.exe") == case["executable_sha256"]
    assert r.sha(r.BUILD / "PvZPvPNative.exe") == r.sha(r.STAGE / "PvZPvPNative.exe") == r.read(r.OUT / "stage.json")["exe_sha256"]
    prior = r.read(r.OUT / "promotion-before.json")["previous"].get("full_regression_report")
    mobile = r.read(r.OUT.parent / "android/interaction.json")
    apk = r.read(r.OUT / "android-package-verification.json")
    assert mobile["passed"] and mobile["apk_sha256"] == apk["sha256"]
    for variant in ("lottery", "izombie"):
        for role in ("host", "guest"):
            log = r.OUT.parent / ("lan-final-" + variant) / (role + ".log")
            result = log.read_text("utf8", errors="replace")
            assert "PASS battle reached" in result
            if r2:
                assert "curtain, reward flight and prep observed" in result
                for step in ("curtain", "rewards", "claim", "prep"):
                    assert (log.parent / f"{role}-{step}.png").is_file()
    return dict(targeted_verification_passed=True, targeted_report=case["report"],
                android_emulator_interaction_verified=True, lan_loopback_verified=True,
                full_regression_rerun=False, full_regression_passed=None,
                previous_full_regression_report=prior, full_regression_report=prior)


r.regression_status = regression_status
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--r4", action="store_true")
    parser.add_argument("--r3", action="store_true")
    parser.add_argument("--r2", action="store_true")
    parser.add_argument("phase", choices=["backup", "stage", "smoke", "apk", "packages", "promote"])
    phase = parser.parse_args().phase
    r.OUT.mkdir(exist_ok=True, parents=True)
    if phase == "backup":
        base.previous.backup()
    else:
        if phase == "smoke":
            os.environ["PVP76R3_AUDIT_CASE"] = "pvp78ai" if r4 else "pvp78"
        if phase == "packages":
            base.source_review()
        getattr(r, phase)()
