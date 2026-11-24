"""Local PvP77 release using the established native package and launcher procedure."""
import argparse
from pathlib import Path
import types
import zipfile
import hashlib

import pvp76_release as previous

ROOT = Path(__file__).resolve().parents[1]
release = types.ModuleType("pvp77_package")
release.__file__ = previous.release.__file__
template = previous.SOURCE.replace("PvP76", "PvP77")
template = template.replace("'MANIFEST-PvP77.json','STAGING_STATUS.json'", "'MANIFEST-PvP76.json','MANIFEST-PvP77.json','STAGING_STATUS.json'")
template = template.replace("timeout=300, creationflags", "timeout=1800 if label == 'pvp77' else 300, creationflags")
template = template.replace("['CMakeLists.txt','AGENTS.md','更新说明-PvP77.md'", "['CMakeLists.txt','AGENTS.md','PvP77_更新计划.md','test_results/pvp77/catalog/before.json','test_results/pvp77/catalog/resolved-cards.json','test_results/pvp77/production/results.json','test_results/pvp77/full-suite/summary.json','更新说明-PvP77.md'")
template = template.replace("本地演练 → 测试模式 可体验三个 Boss 和作弊器；合作第 8/16/24 关新增 Boss。", "主界面下方的闯关模式可进入合作、抽奖和我是僵尸。")
exec(compile(template, release.__file__, "exec"), release.__dict__)
release.OUT = ROOT / "test_results/pvp77/release"
release.STAGE = ROOT / "dist/PvZ-PvP-Native-20261123-pvp77-r1"
release.VERSION = "1.6.0.77-typed.20261123-r1"
release.REV, release.PREVIOUS_REV = "pvp77-r1", "pvp76-r3"
release.CODE = 1123079
release.NATIVE_RUN = "pvp77-r1g-20261123"
release.APK_DIR = ROOT / "dist/apk-pvp77-r1-20261123"
release.EXTRA_AUDITS = previous.release.EXTRA_AUDITS + [("pvp76r2_audit","pvp76r2"),("pvp76r3_audit","pvp77")]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE
previous.release = release
previous.SUITE = ROOT / "test_results/pvp77/full-suite/summary.json"
previous.BASELINE = ROOT / "test_results/pvp76/r3/full-suite/summary.json"
previous.REVIEW = ROOT / "test_results/pvp77/full-suite-review.json"

def regression_status():
    summary = release.read(previous.SUITE)
    if not summary["success"] or summary["waivers"]["unexpected_nonpass"]:
        raise ValueError("Unresolved full-suite regression")
    if summary["binary_sha256"]["game"] != release.sha(release.STAGE / "PvZPvPNative.exe"):
        raise ValueError("Staged executable differs from the tested executable")
    return previous.regression_status()

release.regression_status = regression_status

def source_review():
    source = Path(release.read(release.OUT / "promotion-before.json")["previous"]["developer_package"])
    roots = ["src", "tools", "android", "build/typed72-integrated-v44/source/src", "build/typed72-match-v1", "extract/data"]
    tracked = {}
    endings = {".cpp", ".inc", ".h", ".py", ".json", ".sh", ".cmake", ".md"}
    for root in roots:
        for path in (ROOT / root).rglob("*"):
            if path.suffix in endings and path.is_file() and "__pycache__" not in path.parts:
                tracked[path.relative_to(ROOT).as_posix()] = path
    changed = {}
    with zipfile.ZipFile(source) as old:
        info = {item.filename.split("/",1)[-1]:item for item in old.infolist() if not item.is_dir()}
        for rel, path in tracked.items():
            digest = release.sha(path)
            before = hashlib.sha256(old.read(info[rel])).hexdigest() if rel in info else None
            if before != digest:
                changed[rel] = {"before":before,"after":digest}
    release.dump(release.OUT/"source-change-review.json", {"baseline":str(source),"files":changed})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["backup","stage","smoke","apk","packages","promote"])
    phase = parser.parse_args().phase
    release.OUT.mkdir(parents=True,exist_ok=True)
    if phase == "backup":
        previous.backup()
    else:
        if phase == "packages":
            source_review()
        getattr(release,phase)()
