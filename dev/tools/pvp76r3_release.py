"""PvP76 r3 release phases (run each separately): backup, stage, smoke, apk, packages, promote.

Same reviewed procedure as tools/pvp76_release.py (PvP76 r1) with the r3 identity:
backup-latest becomes the pvp76-r2 rollback group, the full regression is compared with the
r2 suite, and the r2 / r3 kernel audits (pvp76r2_audit, pvp76r3_audit) join the packaged checks.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import pvp76_release as base  # noqa: E402  (builds the 74.4-derived release module)

release = base.release
release.OUT = ROOT / 'test_results/pvp76/r3/release-r3-20261123'
release.STAGE = ROOT / 'dist/PvZ-PvP-Native-20261123-pvp76-r3'
release.VERSION = '1.6.0.76-typed.20261123-r3'
release.REV = 'pvp76-r3'
release.PREVIOUS_REV = 'pvp76-r2'
release.CODE = 1123078
release.NATIVE_RUN = 'pvp76-r3e-20261123'
release.APK_DIR = ROOT / 'dist/apk-pvp76-r3-20261123'
release.EXTRA_AUDITS = base.release.EXTRA_AUDITS + [('pvp76r2_audit', 'pvp76r2'), ('pvp76r3_audit', 'pvp76r3')]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE
base.SUITE = ROOT / 'test_results/pvp76/r3/full-suite/summary.json'
base.BASELINE = ROOT / 'test_results/pvp76/r2/full-suite/summary.json'  # pvp76-r2
base.REVIEW = ROOT / 'test_results/pvp76/r3/full-suite-review.json'


def regression_status():
    status = base.regression_status()
    summary = release.read(base.SUITE)
    if (not summary['success'] or summary['waivers']['unexpected_nonpass'] or not summary['fire_gate']['passed']
            or summary['binary_sha256']['game'] != release.sha(release.STAGE / 'PvZPvPNative.exe')):
        raise ValueError('PvP76 r3 requires accepted regression coverage and matching staged EXE')
    resume = summary.get('resumed')
    if resume and resume['reused_modules']:
        status.update(full_regression_rerun=False, full_regression_resumed=True,
                      full_regression_executed_modules=resume['executed_modules'],
                      full_regression_reused_modules=resume['reused_modules'], full_regression_resume_evidence=resume['evidence'])
    return status


release.regression_status = regression_status


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['backup', 'stage', 'smoke', 'apk', 'packages', 'promote'])
    phase = p.parse_args().phase
    release.OUT.mkdir(parents=True, exist_ok=True)
    if phase == 'backup': base.backup()
    else: getattr(release, phase)()
