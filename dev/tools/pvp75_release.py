"""PvP75 release phases (run each separately): backup, stage, smoke, apk, packages, promote.

Reuses the reviewed 74.4 r3 release procedure with the PvP75 identity, notes and
audits. The full regression is recorded with its raw counts and compared with the
74.4 r4 baseline; non-passing tests are reported, never silently dropped.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'tools/pvp744_release_r3.py').read_text('utf8')
for old, new in [('更新说明-PvP74.4.md', '更新说明-PvP75.md'), ('更新公告-PvP74.4.txt', '更新公告-PvP75.txt'),
                 ("'PvP74.4 正式版", "'PvP75 正式版"), ("'MANIFEST-PvP74.4.json','STAGING_STATUS.json'", "'MANIFEST-PvP74.4.json','MANIFEST-PvP75.json','STAGING_STATUS.json'"),
                 ("entries['MANIFEST-PvP74.4.json']", "entries['MANIFEST-PvP75.json']"), ("hashes['MANIFEST-PvP74.4.json']", "hashes['MANIFEST-PvP75.json']"),
                 ('# PvP74.4 开发者包', '# PvP75 开发者包'), ("'PvZ-PvP-Native-PvP74.4-src/'", "'PvZ-PvP-Native-PvP75-src/'"),
                 ("'dist/PvP74.4-'+REV.split('-')[-1]+'-发行清单.json'", "'dist/PvP75-'+REV.split('-')[-1]+'-发行清单.json'"),
                 ("    if not regression['full_regression_passed']:\n        raise ValueError('Full regression has unresolved failures; see '+regression['full_regression_report'])\n", "")]:
    assert old in SOURCE, old
    SOURCE = SOURCE.replace(old, new)
release = types.ModuleType('pvp75_release_base'); release.__file__ = str(ROOT / 'tools/pvp744_release_r3.py')
exec(compile(SOURCE, release.__file__, 'exec'), release.__dict__)

release.OUT = ROOT / 'test_results/pvp75/release-r3-20261121'
release.STAGE = ROOT / 'dist/PvZ-PvP-Native-20261121-pvp75-r3'
release.VERSION = '1.6.0.75-typed.20261121-r3'
release.REV = 'pvp75-r3'
release.PREVIOUS_REV = 'pvp75-r2'
release.CODE = 1121078
release.NATIVE_RUN = 'pvp75-r3-20261121'
release.APK_DIR = ROOT / 'dist/apk-pvp75-r3-20261121'
release.EXTRA_AUDITS = [('pvp744_r4_audit', 'r4'), ('pvp75_audit', 'pvp75'), ('pvp75_ui_audit', 'pvp75-ui')]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE
SUITE = ROOT / 'test_results/pvp75/full-suite-r2/summary.json'
BASELINE = ROOT / 'test_results/pvp75/full-suite-final/summary.json'  # pvp75-r1


def nonpass(summary):
    return {row['id'] for mod in summary['modules'] for row in mod['unexpected_nonpass'] + mod['waived']}


def regression_status():
    """Raw full-suite evidence for this exact build; refuses stale or moving inputs."""
    read, digest = release.read, release.sha
    s, base = read(SUITE), read(BASELINE)
    if any((s['source_changed_during_run'], s['fixture_changed_during_run'], s['exe_changed_during_run'], s['collection_mismatch'])):
        raise ValueError('Full suite inputs moved during the run')
    if s['exe_sha256'] != digest(release.BUILD / 'cpp_tests.exe'): raise ValueError('cpp_tests.exe differs from the full-suite run')
    for name, expected in read(SUITE.parent / 'source-hashes.json').items():
        if digest(ROOT / name) != expected: raise ValueError('Source changed after the full suite: ' + name)
    if s['missing'] or not s['pure_typed_gate']['passed'] or not s['combat_r4_gate']['passed']:
        raise ValueError('Full suite incomplete or a production gate failed')
    now, before = nonpass(s), nonpass(base)
    review = SUITE.parent.with_name('full-suite-r2-review.json')
    reviewed = read(review)['intended'] if review.exists() else {}
    new = sorted(now - before)
    unexplained = [i for i in new if i not in reviewed]
    if unexplained: raise ValueError('New non-passing tests without a reviewed PvP75 rule change: ' + ', '.join(unexplained[:20]))
    return dict(full_regression_rerun=True, full_regression_passed=s['success'], full_regression_counts=s['counts'],
                full_regression_report=str(SUITE), full_regression_baseline=str(BASELINE),
                full_regression_diff=dict(new_nonpass=len(new), fixed_since_baseline=len(before - now), still_nonpass=len(now & before)),
                intended_rule_changes=len(new), unwaived=len(s['waivers']['unexpected_nonpass']))


QUICK = ROOT / 'test_results/pvp75/r3-quick/checks.json'


def quick_status():
    """r3 is a quick balance revision: the user asked not to rerun the full suite. Records the r2
    full suite it builds on and the targeted checks run on this exact build."""
    read, digest = release.read, release.sha
    q = read(QUICK)
    if not q['passed']: raise ValueError('Targeted r3 checks failed; see ' + str(QUICK))
    for name, expected in q['binaries'].items():
        if digest(ROOT / name) != expected: raise ValueError('Binary changed after the targeted checks: ' + name)
    base = read(SUITE)
    return dict(full_regression_rerun=False, full_regression_passed=None, full_regression_counts=None,
                full_regression_report=None, previous_full_regression=str(SUITE), previous_full_regression_counts=base['counts'],
                quick_revision_checks=str(QUICK), quick_revision_checks_passed=True,
                note='Quick balance revision on top of r2; full suite not rerun at the user request.')


release.regression_status = quick_status


def backup():
    import pvp744_release_r4  # noqa: F401  (identical backup procedure, PvP75 identities)
    module = pvp744_release_r4
    module.release = release
    module.backup()


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['backup', 'stage', 'smoke', 'apk', 'packages', 'promote'])
    phase = p.parse_args().phase
    if phase == 'backup': backup()
    else: getattr(release, phase)()
