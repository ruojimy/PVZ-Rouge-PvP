"""PvP76 r2 release phases (run each separately): backup, stage, smoke, apk, packages, promote.

Same reviewed procedure as tools/pvp76_release.py (PvP76 r1) with the r2 identity:
backup-latest becomes the pvp76-r1 rollback group, the full regression is compared with the
r1 suite, and the r2 kernel audit (pvp76r2_audit) joins the packaged checks.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import pvp76_release as base  # noqa: E402  (builds the 74.4-derived release module)

release = base.release
release.OUT = ROOT / 'test_results/pvp76/r2/release-r2-20261122'
release.STAGE = ROOT / 'dist/PvZ-PvP-Native-20261122-pvp76-r2'
release.VERSION = '1.6.0.76-typed.20261122-r2'
release.REV = 'pvp76-r2'
release.PREVIOUS_REV = 'pvp76-r1'
release.CODE = 1122077
release.NATIVE_RUN = 'pvp76-r2b-20261122'  # rebuilt after the extract/data export
release.APK_DIR = ROOT / 'dist/apk-pvp76-r2-20261122'
release.EXTRA_AUDITS = base.release.EXTRA_AUDITS + [('pvp76r2_audit', 'pvp76r2')]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE
base.SUITE = ROOT / 'test_results/pvp76/r2/full-suite/summary.json'
base.BASELINE = ROOT / 'test_results/pvp76/full-suite-versioned-r1/summary.json'  # pvp76-r1
base.REVIEW = ROOT / 'test_results/pvp76/r2/full-suite-review.json'


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['backup', 'stage', 'smoke', 'apk', 'packages', 'promote'])
    phase = p.parse_args().phase
    release.OUT.mkdir(parents=True, exist_ok=True)
    if phase == 'backup': base.backup()
    else: getattr(release, phase)()
