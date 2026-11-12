"""Refresh the independent local game directly from the latest delivery ZIP."""
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_NAME = 'PVZ_rougePvP_native'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def file_map(folder):
    return {p.relative_to(folder).as_posix(): digest(p)
            for p in folder.rglob('*') if p.is_file()} if folder.exists() else {}

def main():
    manifest = json.loads((ROOT / 'dist/PVP72-20261104-release-manifest.json').read_text(encoding='utf-8'))
    source = ROOT / 'dist' / Path(manifest['pc']['zip']).name
    assert digest(source) == manifest['pc']['sha256']
    local = ROOT / TARGET_NAME
    old_save = Path(os.environ['APPDATA']) / 'PVZ-PvP-Native/pvp_userdata'
    save_before = file_map(old_save)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    evidence = ROOT / 'test_results' / ('local-play-' + stamp)
    evidence.mkdir()
    expected = {}
    old_exe_hash = digest(local / 'PvZPvPNative.exe') if (local / 'PvZPvPNative.exe').exists() else None
    local.mkdir(exist_ok=True)
    with zipfile.ZipFile(str(source)) as archive:
        indexes = [n for n in archive.namelist() if n.endswith('/SHA256SUMS')]
        assert len(indexes) == 1
        prefix = indexes[0][:-len('SHA256SUMS')]
        for line in archive.read(indexes[0]).decode('utf-8').splitlines():
            h, rel = line.split('  ', 1)
            rel = rel[2:] if rel.startswith('./') else rel
            dest = (local / rel).resolve()
            assert os.path.commonpath([str(local.resolve()), str(dest)]) == str(local.resolve())
            payload = archive.read(prefix + rel)
            assert hashlib.sha256(payload).hexdigest() == h, rel
            expected[rel] = h
            # A user's relay endpoint remains configuration rather than payload.
            if rel == 'relay.json' and dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
    assert digest(local / 'PvZPvPNative.exe') == expected['PvZPvPNative.exe']
    assert all(digest(local / rel) == h for rel, h in expected.items() if rel != 'relay.json')
    save = local / 'pvp_userdata'
    save.mkdir(exist_ok=True)
    inherited = []
    for rel in save_before:
        dest = save / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(old_save / rel), str(dest))
        inherited.append(rel)
    assert file_map(old_save) == save_before
    for rel in inherited:
        assert digest(save / rel) == save_before[rel]
    launcher = ('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
                'set "PVP_USERDATA=%~dp0pvp_userdata"\r\n'
                'if not exist "%PVP_USERDATA%" mkdir "%PVP_USERDATA%"\r\n'
                '"%~dp0PvZPvPNative.exe" %*\r\nexit /b %errorlevel%\r\n')
    (local / 'launch_pvp.cmd').write_bytes(launcher.encode('ascii'))
    (local / '启动PvP.cmd').write_bytes(b'@echo off\r\ncall "%~dp0launch_pvp.cmd" %*\r\n')
    (ROOT / '启动PvP.cmd').write_bytes(('@echo off\r\ncall "%~dp0' + TARGET_NAME + '\\launch_pvp.cmd" %*\r\n').encode('ascii'))
    note = ('本机游玩目录：双击“启动PvP.cmd”或 launch_pvp.cmd。\n'
            '存档位于本目录 pvp_userdata，已继承已有native存档；以后的游玩只更新本目录存档。\n'
            '更新 dist 交付目录不会覆盖这里的存档。本目录使用完整文件副本，不依赖交付目录或Python。\n'
            '直接双击EXE仍使用程序默认的AppData存档；需要本机独立存档时请使用上述启动脚本。\n'
            '旧Python版目录与存档保持原样；旧规则回放继续使用对应旧版本。\n')
    (local / '本机游玩说明.txt').write_text(note, encoding='utf-8')
    shutil.copy2(str(ROOT / 'docs/PVP72_安卓实机性能测试_20261104.md'), str(local / 'PVP72_安卓实机性能测试_20261104.md'))
    shutil.copy2(str(ROOT / 'docs/PVP72_变更与验收.md'), str(local / 'PVP72_变更与验收.md'))
    # Make the development entry points tolerate a renamed checkout.
    script_changes = []
    for p in (ROOT / 'tools').glob('*.sh'):
        old = p.read_text(encoding='utf-8')
        new = old.replace('cd /c/Users/xiech/Downloads/PVZ-PvP71-Native', 'cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1')
        if new != old:
            p.write_text(new, encoding='utf-8')
            script_changes.append(p.name)
    guide = ('# 本机游玩与项目目录\n\n'
             '项目根目录为 `C:\\Users\\xiech\\Downloads\\PVZ_rougePvP_native`。\n\n'
             '- 根目录的 `启动PvP.cmd`：打开独立本机游玩副本。\n'
             '- `PVZ_rougePvP_native/`：完整可玩文件，仿照Python版的内层游戏目录。\n'
             '- `PVZ_rougePvP_native/pvp_userdata/`：本机独立存档，已继承已有native存档。\n'
             '- `dist/`：仅保留最新PvP72的Windows ZIP、安卓APK、源码检查点及其校验和、发布清单。\n\n'
             '双击根目录或内层的启动脚本游玩；直接启动EXE仍使用AppData默认存档。\n'
             '后续刷新可用嵌入式Python执行 `tools/setup_local_play.py`，直接读取交付ZIP，已有本机存档和relay配置不会覆盖。\n'
             '按要求不另建旧目录备份；dist仅保留最新交付文件，AppData存档原位保留。\n')
    guide += '\n旧路径 `PVZ-PvP71-Native` 仅为指向新项目的目录链接，兼容当前Codex工具进程；没有另一份项目数据。\n'
    (ROOT / 'docs/本机游玩目录说明.md').write_text(guide, encoding='utf-8')
    readme = ROOT / 'README.md'
    text = readme.read_text(encoding='utf-8')
    link = '本机游玩：双击根目录 `启动PvP.cmd`，使用内层 `PVZ_rougePvP_native/pvp_userdata` 独立存档。目录安排见 [本机游玩目录说明](docs/本机游玩目录说明.md)。'
    if link not in text:
        title, rest = text.split('\n', 1)
        readme.write_text(title + '\n\n' + link + '\n' + rest, encoding='utf-8')
    report = {'complete': True, 'backups_created': False, 'source': str(source),
              'local_directory': str(local),
              'old_local_exe_sha256': old_exe_hash, 'installed_exe_sha256': expected['PvZPvPNative.exe'],
              'release_files_verified_per_directory': len(expected),
              'existing_appdata_save_files': len(save_before), 'inherited_save_files': inherited,
              'original_appdata_save_unchanged': True, 'user_relay_preserved': True,
              'independent_regular_file_copy': True, 'relative_shell_entrypoints_updated': script_changes}
    (evidence / 'deployment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'build/local-play-workdir.txt').write_text(str(evidence), encoding='utf-8')
    print(json.dumps({'complete': True, 'verified_files_per_directory': len(expected),
                      'inherited_save_files': len(inherited), 'evidence': str(evidence)}, ensure_ascii=True))

if __name__ == '__main__':
    main()
