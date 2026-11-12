"""Where PvP player data lives, and how older installs hand it over.

Up to PvP60 the PC build kept ``pvp_userdata`` next to the game: inside the
workspace for the developer package, inside the game folder for the release
package. A freshly unpacked release therefore started with no name, record,
settings, replays or maps. From PvP61 the PC build keeps them per Windows user
(``%APPDATA%/PVZ-Rouge-PvP/pvp_userdata``), the same way the original game keeps
its saves in the user's home, so every later package finds them.

Older folders are merged in once, never moved or deleted: files missing in the
per-user folder are copied, match records are unioned, existing files win.
Besides the running install's own folders, the update helper registers the
folders of the install it updated in ``legacy_sources.json``.
``PVP_USERDATA`` (Android, tests, isolated diagnostics) bypasses all of this.

PvP68 directly upgrades PvP67 and retains its per-user folder
(``%APPDATA%/PVZ-Rouge-PvP67/pvp_userdata``). The PvP66 folder is checked
first, then the PvP61-65 folder. Both are read-only migration sources:
missing files are copied and match records are merged; neither source is
changed, moved or deleted. Existing PvP67/68 settings always win.
"""
import json
import os
import shutil
from pathlib import Path

APP_FOLDER = 'PVZ-Rouge-PvP67'
# Per-user folders of earlier versions: read-only sources for the first run.
PREVIOUS_APP_FOLDERS = ('PVZ-Rouge-PvP66', 'PVZ-Rouge-PvP')
LEGACY_INDEX = 'legacy_sources.json'
MIGRATED_INDEX = 'migrated_sources.json'
# AI-version keys and transient files stay with the install that made them.
SKIPPED_PREFIXES = ('ai', 'crash-', 'audit-')
SKIPPED_SUFFIXES = ('.pending',)


def per_user_root(environ=None, folder=APP_FOLDER):
    environ = os.environ if environ is None else environ
    base = environ.get('APPDATA') or environ.get('LOCALAPPDATA')
    if base:
        return Path(base) / folder / 'pvp_userdata'
    return Path.home() / ('.' + folder.lower()) / 'pvp_userdata'


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return default


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    os.replace(str(pending), str(path))


def _key(path):
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except OSError:
        return os.path.normcase(os.path.abspath(str(path)))


def _skipped(relative):
    name = relative.name.lower()
    return name.startswith(SKIPPED_PREFIXES) or name.endswith(SKIPPED_SUFFIXES) or relative.parts[0] in (
        LEGACY_INDEX, MIGRATED_INDEX)


def merge_player(source, target):
    """Union two player.json files; the per-user name wins unless it is default."""
    old = _read_json(source, {})
    new = _read_json(target, None)
    if not isinstance(old, dict):
        return False
    if not isinstance(new, dict):
        shutil.copy2(str(source), str(target))
        return True
    matches = dict(old.get('matches') or {}) if isinstance(old.get('matches'), dict) else {}
    matches.update(new.get('matches') or {} if isinstance(new.get('matches'), dict) else {})
    name = new.get('name')
    if not name or name == '玩家':
        name = old.get('name') or name
    merged = dict(new, format=new.get('format', old.get('format', 'pvp-player-1')), name=name, matches=matches)
    if merged != new:
        _write_json(target, merged)
        return True
    return False


def merge_folder(source, target):
    """Copy what the per-user folder lacks; returns the number of files taken."""
    source, target = Path(source), Path(target)
    copied = 0
    paths = sorted(source.rglob('*'))
    from . import map_deletions
    # Read deletion metadata before copying UUID-named files. A current save's
    # existing decision file wins; maps it already owns also beat old markers.
    for path in paths:
        if path.is_file() and path.name == map_deletions.INDEX and path.parent.name in ('maps', 'custom_maps'):
            destination = target / path.relative_to(source)
            if not destination.exists():
                identifiers = {key for key in map_deletions.read(path.parent)
                               if not (destination.parent / (key + '.json')).exists()}
                map_deletions.write(destination.parent, identifiers)
                copied += 1
    removed = {}
    for path in paths:
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if _skipped(relative):
            continue
        destination = target / relative
        if path.name == map_deletions.INDEX and path.parent.name in ('maps', 'custom_maps'):
            continue
        if map_deletions.map_file(relative):
            if destination.parent not in removed:
                removed[destination.parent] = map_deletions.read(destination.parent)
            if relative.stem in removed[destination.parent]:
                continue
        if relative.as_posix() == 'player.json':
            destination.parent.mkdir(parents=True, exist_ok=True)
            copied += int(merge_player(path, destination))
            continue
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(destination))
        copied += 1
    return copied


def legacy_candidates(workspace, exe_dir, root, environ=None):
    found = [per_user_root(environ, folder) for folder in PREVIOUS_APP_FOLDERS]
    for folder in (workspace, exe_dir, exe_dir.parent if exe_dir else None):
        if folder is not None:
            found.append(Path(folder) / 'pvp_userdata')
    for entry in _read_json(root / LEGACY_INDEX, []):
        if isinstance(entry, str):
            found.append(Path(entry))
    unique = []
    seen = set()
    for folder in found:
        key = _key(folder)
        if key not in seen:
            seen.add(key)
            unique.append(folder)
    return unique


def migrate(root, candidates):
    """Merge each not-yet-merged legacy folder into ``root``; idempotent."""
    root = Path(root)
    done = _read_json(root / MIGRATED_INDEX, [])
    done = [d for d in done if isinstance(d, str)] if isinstance(done, list) else []
    report = []
    for folder in candidates:
        key = _key(folder)
        if key in done or key == _key(root) or not Path(folder).is_dir():
            continue
        try:
            copied = merge_folder(folder, root)
        except OSError as exc:
            report.append((str(folder), 'error: %s' % exc))
            continue
        done.append(key)
        report.append((str(folder), copied))
    if report:
        _write_json(root / MIGRATED_INDEX, done)
    return report


def resolve(workspace, exe_dir, android=False, environ=None):
    """The userdata folder for this process, migrating legacy PC data first."""
    environ = os.environ if environ is None else environ
    override = environ.get('PVP_USERDATA')
    if override:
        return Path(override), []
    if android:
        return Path(workspace) / 'pvp_userdata', []
    root = per_user_root(environ)
    try:
        root.mkdir(parents=True, exist_ok=True)
        report = migrate(root, legacy_candidates(workspace, exe_dir, root, environ))
    except OSError:
        # A read-only profile must not stop the game; fall back to the old
        # location so the player still keeps saving somewhere.
        return Path(workspace) / 'pvp_userdata', []
    return root, report
