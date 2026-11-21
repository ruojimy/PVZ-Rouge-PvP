"""PvP75 feedback test build: stage, audit, and point the root launcher at it.

Not a release. The released pvp75-r1 stage (dist/PvZ-PvP-Native-20261121-pvp75) stays
untouched as the rollback; this build goes to its own stage folder, and the root
launcher folder (PVZ_rougePvP_native) receives only the files that differ. User saves
(launcher pvp_userdata and %APPDATA%) are hashed before and after and must not change.
    python tools/pvp75_testbuild.py stage|audit|launch  --name test1
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/app-typed72-v2/Release'
DEST = ROOT / 'PVZ_rougePvP_native'
# The current formal release (dist/latest-native-release.json): rollback source and launcher files.
RELEASED = Path(json.loads((ROOT / 'dist/latest-native-release.json').read_text('utf8'))['release'])


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tree(folder): return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
def dump(p, obj): Path(p).parent.mkdir(parents=True, exist_ok=True); Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), 'utf8')


def users():
    out = {}
    for folder in [DEST / 'pvp_userdata', Path(os.environ['APPDATA']) / 'PVZ-PvP-Native/pvp_userdata']:
        out[str(folder)] = tree(folder) if folder.is_dir() else None
    return out


def stage(name, stage_dir, out):
    marker = stage_dir / 'release-revision.json'
    if stage_dir.exists():
        assert json.loads(marker.read_text('utf8')).get('test_build') == name, 'refusing to replace a folder this script did not create'
        shutil.rmtree(stage_dir)
    (stage_dir / 'extract').mkdir(parents=True)
    for f in ['PvZPvPNative.exe', 'relay.json'] + [p.name for p in BUILD.glob('SDL2*.dll')]: shutil.copy2(BUILD / f, stage_dir / f)
    for f in ['图片', '音乐', '音效']: shutil.copytree(BUILD / f, stage_dir / f)
    for f in ['extract/data', 'extract/assets', 'fonts']: shutil.copytree(ROOT / f, stage_dir / f)
    for f in ['更新说明-PvP75.md', '更新公告-PvP75.txt']: shutil.copy2(ROOT / f, stage_dir / f)
    shutil.copy2(RELEASED / '启动PvP.cmd', stage_dir / '启动PvP.cmd'); shutil.copy2(RELEASED / '启动说明.txt', stage_dir / '启动说明.txt')
    base = json.loads((RELEASED / 'release-revision.json').read_text('utf8'))
    dump(marker, {**base, 'delivery_revision': 'pvp75-' + name, 'formal_release': False, 'test_build': name,
                  'release_authorized_by_user': False, 'note': 'PvP75 feedback test build for local testing; not a release'})
    dump(out / 'stage.json', dict(exe_sha256=sha(stage_dir / 'PvZPvPNative.exe'), files=len(tree(stage_dir))))
    print('test build staged:', stage_dir)


def audit(stage_dir, out):
    # The shipped exe turns these on from release-revision.json (metadata view etc.); audit the same path.
    flags = {k: str(v) for k, v in json.loads((stage_dir / 'release-revision.json').read_text('utf8'))['default_performance_options'].items()}
    assert flags.get('PVP744_METADATA_VIEW') == '1', flags
    results = []
    for exe, label in [('pvp75_audit', 'kernel'), ('pvp75_ui_audit', 'ui'), ('pvp744_testmode_audit', 'testmode')]:
        folder = out / label
        if folder.exists(): shutil.rmtree(folder)
        folder.mkdir(parents=True)
        env = dict(os.environ, PVZ_TEST_ROOT=str(stage_dir), PVP_USERDATA=str(folder / 'userdata'),
                   SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software', **flags)
        with (folder / 'audit.log').open('wb') as log:
            r = subprocess.run([str(BUILD / (exe + '.exe')), str(folder)], cwd=stage_dir, env=env, stdout=log,
                               stderr=subprocess.STDOUT, timeout=900, creationflags=0x08000000)
        report = json.loads((folder / 'results.json').read_text('utf8'))
        failures = report.get('failures', report.get('errors', 0))
        results.append(dict(audit=label, exit=r.returncode, failures=failures, flags=flags))
        print(label, 'exit', r.returncode, 'failures', failures, flush=True)
    dump(out / 'audits.json', results)
    assert all(x['exit'] == 0 and not x['failures'] for x in results), results


def launch(name, stage_dir, out):
    import psutil
    exe = (DEST / 'PvZPvPNative.exe').resolve()
    running = [p.info['pid'] for p in psutil.process_iter(['pid', 'exe']) if p.info['exe'] and Path(p.info['exe']).resolve() == exe]
    assert not running, 'The game is running from the launcher folder: ' + str(running)
    assert '%~dp0pvp_userdata' in (DEST / 'launch_pvp.cmd').read_text('utf-8-sig')
    before = users(); dump(out / 'userdata-before.json', before)
    payload = tree(stage_dir); changed = []
    for rel, digest in payload.items():
        target = DEST / rel
        if target.exists() and sha(target) == digest: continue
        target.parent.mkdir(parents=True, exist_ok=True); temp = target.with_name(target.name + '.next')
        if temp.exists(): temp.unlink()
        shutil.copy2(stage_dir / rel, temp); assert sha(temp) == digest; os.replace(temp, target); changed.append(rel)
    assert all(sha(DEST / rel) == digest for rel, digest in payload.items())
    after = users(); assert after == before, 'user saves changed'
    record = dict(launcher=str(ROOT / '启动PvP.cmd'), target=str(DEST / 'PvZPvPNative.exe'), exe_sha256=sha(DEST / 'PvZPvPNative.exe'),
                  stage=str(stage_dir), test_build=name, updated_at=datetime.now().isoformat(), changed_files=len(changed),
                  userdata_files_verified=sum(len(v or {}) for v in before.values()),
                  rollback=str(RELEASED) + ' (released pvp75-r1; re-sync its files to restore)',
                  note='Root launcher runs a PvP75 feedback test build, not a release.')
    dump(out / 'launch.json', record); dump(ROOT / 'dist/launcher-test-build.json', record)
    print('launcher now runs', name, record['exe_sha256'], len(changed), 'files changed')


def restore():
    """Point the launcher back at the released stage (before a formal release's backup/promote)."""
    record = ROOT / 'dist/launcher-test-build.json'
    launch('released', RELEASED, ROOT / 'test_results/pvp75/testbuild-restore')
    released = json.loads((ROOT / 'dist/latest-native-release.json').read_text('utf8'))
    assert sha(DEST / 'PvZPvPNative.exe') == released['exe_sha256'], 'launcher does not match the released EXE'
    record.unlink()
    print('launcher restored to', released['revision'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase', choices=['stage', 'audit', 'launch', 'restore']); ap.add_argument('--name', default='test1')
    a = ap.parse_args()
    stage_dir = ROOT / ('dist/PvZ-PvP-Native-20261121-pvp75-' + a.name); out = ROOT / 'test_results/pvp75' / ('testbuild-' + a.name)
    {'stage': lambda: stage(a.name, stage_dir, out), 'audit': lambda: audit(stage_dir, out), 'launch': lambda: launch(a.name, stage_dir, out), 'restore': restore}[a.phase]()
