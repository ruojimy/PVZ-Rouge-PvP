"""Build the PvP77 r4 hotfix using its scoped production acceptance report."""
import argparse
import os
from pathlib import Path
import pvp77_release as base

r = base.release
source = base.template.replace("('pvp744_testmode_audit','boss')", "('pvp76r3_audit','pvp77')")
start = source.index("    cases = ", source.index("def smoke():"))
end = source.index("    results = []", start)
source = source[:start] + "    cases = [('pvp76r3_audit','pvp77')]\n" + source[end:]
source = source.replace("'test_results/pvp77/full-suite/summary.json','更新说明", "'test_results/pvp77/full-suite/summary.json','test_results/pvp77/r4/release/packaged-gift-pvp77/results.json','更新说明")
exec(compile(source, r.__file__, "exec"), r.__dict__)
r.OUT = base.ROOT / "test_results/pvp77/r4/release"
r.STAGE = base.ROOT / "dist/PvZ-PvP-Native-20261124-pvp77-r4"
r.VERSION = "1.6.0.77-typed.20261124-r4"
r.REV, r.PREVIOUS_REV = "pvp77-r4", "pvp77-r3"
r.CODE, r.NATIVE_RUN = 1123082, "pvp77-r4b-20261124"
r.APK_DIR = base.ROOT / "dist/apk-pvp77-r4-20261124"
r.helpers.VERSION,r.helpers.OUT,r.helpers.STAGE = r.VERSION,r.OUT,r.STAGE
base.previous.release = r

def scoped_status():
    smoke = r.read(r.OUT / "pc-smoke-verification.json")
    features = r.read(r.OUT / "packaged-feature-verification.json")
    case = features["cases"][0]
    tested = r.read(Path(case["report"]))
    groups = tested["checks"][0]
    expected = {"cart.小鬼炮","cart.投篮车僵尸","armor.frames"}
    assert groups["name"]=="pvp77r4" and groups["passed"] and {case["id"] for case in groups["evidence"]}==expected
    assert all(x["passed"] for x in groups["evidence"]) and not tested["failures"]
    assert smoke["passed"] and features["passed"] and case["executable_sha256"]==r.sha(r.BUILD/"pvp76r3_audit.exe")
    assert r.sha(r.STAGE/"PvZPvPNative.exe")==r.sha(r.BUILD/"PvZPvPNative.exe")==r.read(r.OUT/"stage.json")["exe_sha256"]
    return dict(full_regression_rerun=False,full_regression_passed=None,
                targeted_verification_passed=True,targeted_report=case["report"],
                previous_full_regression_report=str(base.ROOT/"test_results/pvp77/full-suite/summary.json"),
                full_regression_report=str(base.ROOT/"test_results/pvp77/full-suite/summary.json"))

r.regression_status = scoped_status
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["backup","stage","smoke","apk","packages","promote"])
    phase=parser.parse_args().phase
    r.OUT.mkdir(exist_ok=True,parents=True)
    if phase=="backup":
        base.previous.backup()
    else:
        if phase=="smoke":os.environ["PVP76R3_AUDIT_CASE"]="pvp77r4"
        if phase=="packages":base.source_review()
        getattr(r,phase)()
