"""PvP73 PC package: dist/PvZ-PvP-Native-<id>/ from the previous release folder plus the new EXE,
data identity and notes; SHA256SUMS; ZIP whose single top folder is "PvZ-PvP-Native" (extract over
the old folder to upgrade); independent checks:
  1. every file against SHA256SUMS, EXE == built EXE
  2. ZIP unpack + real entry --smoke-report from an unrelated cwd (must start a typed72 session)
  3. upgrade-over-old: unpack the previous release as PvZ-PvP-Native, plant a stale file, extract the
     new ZIP over it, start the game once: the stale file is removed, upgrade-cleanup.txt names it,
     user data untouched.
Usage: package_pc73.py <id> <previous-release-dir>"""
import hashlib, json, os, shutil, subprocess, sys, time, zipfile
from pathlib import Path
ROOT = Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
ID, PREV = sys.argv[1], ROOT / sys.argv[2]
BUILD = ROOT / 'build/app-typed72-v2/Release'
pc = ROOT / 'dist' / ('PvZ-PvP-Native-' + ID)
ev = ROOT / 'test_results/pvp73' / ('pc-package-' + ID)
assert not pc.exists() and not ev.exists()
ev.mkdir(parents=True)
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
out = {'candidate': str(pc), 'previous': str(PREV)}
# 0. assemble
shutil.copytree(PREV, pc)
for f in ('SHA256SUMS',):
    (pc / f).unlink()
shutil.copy2(BUILD / 'PvZPvPNative.exe', pc / 'PvZPvPNative.exe')
for dll in ('SDL2.dll', 'SDL2_image.dll', 'SDL2_mixer.dll', 'SDL2_ttf.dll'):
    shutil.copy2(BUILD / dll, pc / dll)
shutil.copy2(ROOT / 'extract/data/__init__.json', pc / 'extract/data/__init__.json')
shutil.copy2(ROOT / 'build/pvp73-tools/启动说明-PvP73.txt', pc / '启动说明.txt')
(pc / '更新说明-PvP73.txt').write_bytes((ROOT / '更新说明-PvP73.md').read_text('utf-8').replace('\n', '\r\n').encode('utf-8-sig'))
for stray in list(pc.glob('crash-*.txt')) + list(pc.glob('reports')):
    shutil.rmtree(stray) if stray.is_dir() else stray.unlink()
names = sorted(p.relative_to(pc).as_posix() for p in pc.rglob('*') if p.is_file())
(pc / 'SHA256SUMS').write_text(''.join('%s *./%s\n' % (sha(pc / n), n) for n in names), encoding='utf-8')
# 1. manifest
bad = []
for line in (pc / 'SHA256SUMS').read_text('utf-8').splitlines():
    digest, name = line.split(None, 1); name = name.lstrip('*').lstrip('./')
    if sha(pc / name) != digest: bad.append(name)
out['files'] = len(names); out['mismatch'] = bad
out['exe_sha256'] = sha(pc / 'PvZPvPNative.exe'); assert out['exe_sha256'] == sha(BUILD / 'PvZPvPNative.exe') and not bad
# 2. zip with a fixed top folder
archive = pc.with_suffix('.zip')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in sorted(pc.rglob('*')):
        if p.is_file(): z.write(p, 'PvZ-PvP-Native/' + p.relative_to(pc).as_posix())
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
out['zip'] = str(archive); out['zip_sha256'] = sha(archive)
archive.with_suffix('.zip.sha256').write_text(out['zip_sha256'] + ' *' + archive.name + '\n', encoding='utf-8')
unpacked = ev / 'unpacked'; unpacked.mkdir()
with zipfile.ZipFile(archive) as z: z.extractall(unpacked)
root = unpacked / 'PvZ-PvP-Native'; assert sha(root / 'PvZPvPNative.exe') == out['exe_sha256']
launch = ev / 'launch-cwd'; launch.mkdir(); report = ev / 'smoke-report.json'
env = dict(os.environ, PVP_USERDATA=str(ev / 'userdata'), SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
t0 = time.time()
with open(ev / 'smoke-stdout.txt', 'wb') as so, open(ev / 'smoke-stderr.txt', 'wb') as se:
    rc = subprocess.run([str(root / 'PvZPvPNative.exe'), '--smoke-report', str(report)], cwd=str(launch), env=env, stdout=so, stderr=se, timeout=900).returncode
res = json.loads(report.read_text('utf-8')) if report.exists() else {}
typed = [l for l in (ev / 'smoke-stderr.txt').read_text('utf-8', errors='replace').splitlines() if '[typed72] battle session started' in l]
out.update(smoke_exit=rc, smoke_seconds=round(time.time() - t0, 1), smoke_passed=bool(res.get('passed')), typed_session_lines=typed)
# 3. upgrade over the previous release folder
up = ev / 'upgrade'; up.mkdir(); old = up / 'PvZ-PvP-Native'
shutil.copytree(PREV, old)
stale = old / '图片' / 'pvp72-only-stale.png'; stale.write_bytes(b'stale')
userdata = up / 'userdata'; userdata.mkdir(); (userdata / 'installed-build.txt').write_text('1.6.0.72-native.20261104\n', encoding='utf-8')
(userdata / 'keep.json').write_text('{"keep": true}', encoding='utf-8')
with zipfile.ZipFile(archive) as z: z.extractall(up)
env2 = dict(os.environ, PVP_USERDATA=str(userdata), SDL_AUDIODRIVER='dummy')
p = subprocess.Popen([str(old / 'PvZPvPNative.exe')], cwd=str(old), env=env2)
try: p.wait(timeout=12)
except subprocess.TimeoutExpired: p.kill(); p.wait()
log = (userdata / 'upgrade-cleanup.txt').read_text('utf-8') if (userdata / 'upgrade-cleanup.txt').exists() else ''
out['upgrade'] = dict(stale_removed=not stale.exists(), cleanup_log=log[-600:],
                      marker=(userdata / 'installed-build.txt').read_text('utf-8').strip(),
                      userdata_kept=(userdata / 'keep.json').exists(),
                      exe_is_new=sha(old / 'PvZPvPNative.exe') == out['exe_sha256'])
# 4. PvP72 and older wrote no marker: an existing player.json alone must count as an upgrade (notice shown),
#    a brand-new userdata must not.
def first_start(tag, with_save):
    root4 = ev / tag; shutil.copytree(PREV, root4 / 'PvZ-PvP-Native')
    with zipfile.ZipFile(archive) as z: z.extractall(root4)
    ud = root4 / 'userdata'; ud.mkdir()
    if with_save: (ud / 'player.json').write_text('{"name": "old"}', encoding='utf-8')
    q = subprocess.Popen([str(root4 / 'PvZ-PvP-Native' / 'PvZPvPNative.exe')], cwd=str(root4 / 'PvZ-PvP-Native'), env=dict(os.environ, PVP_USERDATA=str(ud), SDL_AUDIODRIVER='dummy'))
    try: q.wait(timeout=12)
    except subprocess.TimeoutExpired: q.kill(); q.wait()
    log4 = (ud / 'upgrade-cleanup.txt').read_text('utf-8') if (ud / 'upgrade-cleanup.txt').exists() else ''
    return dict(notice=[l for l in log4.splitlines() if l.startswith('notice:')], marker=(ud / 'installed-build.txt').read_text('utf-8').strip() if (ud / 'installed-build.txt').exists() else '')
out['unmarked_upgrade'] = first_start('unmarked-upgrade', True)
out['fresh_install'] = first_start('fresh-install', False)
out['passed'] = bool(rc == 0 and res.get('passed') and typed and out['upgrade']['stale_removed'] and out['upgrade']['userdata_kept']
                     and out['upgrade']['exe_is_new'] and out['upgrade']['marker'].startswith('1.6.0.73')
                     and len(out['unmarked_upgrade']['notice']) == 1 and 'PvP72 或更早' in out['unmarked_upgrade']['notice'][0]
                     and not out['fresh_install']['notice'] and out['fresh_install']['marker'].startswith('1.6.0.73'))
(ev / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])
