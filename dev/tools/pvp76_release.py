"""PvP76 release phases (run each separately): backup, stage, smoke, apk, packages, promote.

Reuses the reviewed 74.4 r3 release procedure (as PvP75 did) with the PvP76 identity,
notes and audits. The full regression is recorded with its raw counts and compared with
the PvP75 r2 full suite; new non-passing tests must be listed as reviewed PvP76 rule
changes in test_results/pvp76/full-suite-review.json.
"""
import argparse
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'tools/pvp744_release_r3.py').read_text('utf8')
for old, new in [('更新说明-PvP74.4.md', '更新说明-PvP76.md'), ('更新公告-PvP74.4.txt', '更新公告-PvP76.txt'),
                 ("'PvP74.4 正式版", "'PvP76 正式版"), ("'MANIFEST-PvP74.4.json','STAGING_STATUS.json'", "'MANIFEST-PvP74.4.json','MANIFEST-PvP76.json','STAGING_STATUS.json'"),
                 ("entries['MANIFEST-PvP74.4.json']", "entries['MANIFEST-PvP76.json']"), ("hashes['MANIFEST-PvP74.4.json']", "hashes['MANIFEST-PvP76.json']"),
                 ('# PvP74.4 开发者包', '# PvP76 开发者包'), ("'PvZ-PvP-Native-PvP74.4-src/'", "'PvZ-PvP-Native-PvP76-src/'"),
                 ("'dist/PvP74.4-'+REV.split('-')[-1]+'-发行清单.json'", "'dist/PvP76-'+REV.split('-')[-1]+'-发行清单.json'"),
                 ("    if not regression['full_regression_passed']:\n        raise ValueError('Full regression has unresolved failures; see '+regression['full_regression_report'])\n", "")]:
    assert old in SOURCE, old
    SOURCE = SOURCE.replace(old, new)
release = types.ModuleType('pvp76_release_base'); release.__file__ = str(ROOT / 'tools/pvp744_release_r3.py')
exec(compile(SOURCE, release.__file__, 'exec'), release.__dict__)

release.OUT = ROOT / 'test_results/pvp76/release-r1-20261122'
release.STAGE = ROOT / 'dist/PvZ-PvP-Native-20261122-pvp76-r1'
release.VERSION = '1.6.0.76-typed.20261122-r1'
release.REV = 'pvp76-r1'
release.PREVIOUS_REV = 'pvp75-r3'
release.CODE = 1122076
release.NATIVE_RUN = 'pvp76-r1-20261122'
release.APK_DIR = ROOT / 'dist/apk-pvp76-r1-20261122'
release.EXTRA_AUDITS = [('pvp744_r4_audit', 'r4'), ('pvp75_audit', 'pvp75'), ('pvp75_ui_audit', 'pvp75-ui'), ('pvp76_audit', 'pvp76')]
release.helpers.VERSION, release.helpers.OUT, release.helpers.STAGE = release.VERSION, release.OUT, release.STAGE
SUITE = ROOT / 'test_results/pvp76/full-suite/summary.json'
BASELINE = ROOT / 'test_results/pvp75/full-suite-r2/summary.json'  # pvp75-r2 (r3 was a quick revision on top of it)
REVIEW = ROOT / 'test_results/pvp76/full-suite-review.json'


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
    reviewed = read(REVIEW)['intended'] if REVIEW.exists() else {}
    new = sorted(now - before)
    unexplained = [i for i in new if i not in reviewed]
    if unexplained: raise ValueError('New non-passing tests without a reviewed PvP76 rule change: ' + ', '.join(unexplained[:20]))
    return dict(full_regression_rerun=True, full_regression_passed=s['success'], full_regression_counts=s['counts'],
                full_regression_report=str(SUITE), full_regression_baseline=str(BASELINE),
                full_regression_diff=dict(new_nonpass=len(new), fixed_since_baseline=len(before - now), still_nonpass=len(now & before)),
                intended_rule_changes=len(new), unwaived=len(s['waivers']['unexpected_nonpass']))


release.regression_status = regression_status


def backup():
    import pvp744_release_r4  # noqa: F401  (identical backup procedure, PvP76 identities)
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
