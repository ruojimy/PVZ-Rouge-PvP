"""Minimal owned/gen/frozen text sync; never changes tracking geometry or numbers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGES = [
    ('横纵2.75格内', '约4.6格（标准地图）内'),
    ('（约2.75格内且可见）', '（标准地图约4.6格内且可见）'),
    ('约2.75格', '约4.6格（标准地图）'),
]
TEXT_FILES = [
    'tools/pvp72_sources/catalog.py',
    'tools/pvp72_sources/pvp71_catalog.py',
    'tools/pvp72_sources/almanac_text.py',
    'src/sim/pvp/gen/pm_catalog.cpp',
    'src/sim/pvp/gen/pm_pvp71_catalog.cpp',
    'src/sim/pvp/gen/pm_almanac_text.cpp',
    'build/typed72-integrated-v44/source/src/sim/typed/cold_catalog_data.cpp',
    'tools/typed72/drafts/cold_catalog_data.cpp',
]
UNCHANGED = [
    'build/typed72-integrated-v44/source/src/sim/typed/native_tracking.cpp',
    'tools/pvp72_sources/native_battle.py',
    'tools/pvp72_sources/pve_ui.py',
    'src/ui/gen/pm_pve_ui.cpp',
    'src/ui/gen/pm_app.cpp',
]
CARDS = {'plant:香蒲', 'secret:猫尾', 'plant:路灯花'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def changed(text):
    for before, after in CHANGES:
        text = text.replace(before, after)
    return text


def differences(before, after, path=()):
    if type(before) != type(after):
        raise RuntimeError('non-text JSON shape changed: ' + repr(path))
    if isinstance(before, dict):
        if list(before) != list(after):
            raise RuntimeError('JSON keys/order changed: ' + repr(path))
        return sum((differences(before[key], after[key], path + (key,)) for key in before), [])
    if isinstance(before, list):
        if len(before) != len(after):
            raise RuntimeError('JSON list changed: ' + repr(path))
        return sum((differences(a, b, path + (i,)) for i, (a, b) in enumerate(zip(before, after))), [])
    if before == after:
        return []
    legal_path = (path == ('MARK_TEXT',)
                  or len(path) == 2 and path[0] == 'NOTES' and path[1] in CARDS
                  or len(path) >= 2 and path[-2] in CARDS
                  and path[-1] in {'description', 'native_description'})
    if not isinstance(before, str) or after != changed(before) or not legal_path:
        raise RuntimeError('unapproved JSON change: ' + repr(path))
    return [{'path': list(path), 'before': before, 'after': after}]


def main():
    immutable = {rel: digest((ROOT / rel).read_bytes()) for rel in UNCHANGED}
    plan, rows = [], []
    for rel in TEXT_FILES:
        path = ROOT / rel
        raw = path.read_bytes()
        text = raw.decode('utf8')
        result = changed(text).encode('utf8')
        if raw == result:
            raise RuntimeError('expected old text missing before one-shot sync: ' + rel)
        if '2.75格' in result.decode('utf8'):
            raise RuntimeError('old descriptor remains: ' + rel)
        rows.append({'file': rel, 'before_sha256': digest(raw), 'after_sha256': digest(result),
                     'replacements': sum(text.count(old) for old, _ in CHANGES)})
        plan.append((path, result))
    data_fields = 0
    for path in sorted((ROOT / 'extract/data').glob('*.json')):
        raw = path.read_bytes()
        result = changed(raw.decode('utf8')).encode('utf8')
        if result == raw:
            continue
        delta = differences(json.loads(raw), json.loads(result))
        data_fields += len(delta)
        rows.append({'file': path.relative_to(ROOT).as_posix(),
                     'before_sha256': digest(raw), 'after_sha256': digest(result),
                     'text_fields': delta, 'non_text_fields_changed': False})
        plan.append((path, result))
    for path, raw in plan:
        path.write_bytes(raw)
    after = {rel: digest((ROOT / rel).read_bytes()) for rel in UNCHANGED}
    if immutable != after:
        raise RuntimeError('combat or layout source changed during text sync')
    report = {'passed': True, 'scope': 'Only tracking-mark descriptions; 220px combat and layout2.75 unchanged.',
              'data_text_fields_changed': data_fields, 'files': rows,
              'unchanged_combat_and_layout_sha256': immutable}
    output = ROOT / 'test_results/pvp742/cattail-mark-text-sync.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
    print(json.dumps({'passed': True, 'files': len(rows), 'data_text_fields': data_fields,
                      'report': output.relative_to(ROOT).as_posix()}))


if __name__ == '__main__':
    main()
