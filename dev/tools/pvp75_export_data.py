"""PvP75: refresh the exported static tables of the owned catalog modules.

Same rule as tools/pvp72_export_data.py (update keys that already exist; never
write into the 71 reference), with the build id passed explicitly:
    python tools/pvp75_export_data.py 1.6.0.75-typed.YYYYMMDD
Without an argument the current extract/data/__init__.json BUILD is kept.
"""
import importlib, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
reference = Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71')
sys.path[:0] = [str(root / 'tools'), str(reference / 'modkit')]
init = root / 'extract/data/__init__.json'
build = sys.argv[1] if len(sys.argv) > 1 else json.loads(init.read_text(encoding='utf8'))['BUILD']
import pvp
pvp.__path__.insert(0, str(root / 'tools/pvp72_sources'))
pvp.BUILD = build
from export_data import plain, Skip
for name in 'balance catalog pvp58_catalog pvp71_catalog zombie_secret_catalog pvp66_secrets zombie_secrets'.split():
    module = importlib.import_module('pvp.' + name)
    path = root / 'extract/data' / (name + '.json')
    old = json.loads(path.read_text(encoding='utf8'))
    for key in list(old):
        if hasattr(module, key):
            try: old[key] = plain(getattr(module, key))
            except Skip: pass
    path.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf8')
old = json.loads(init.read_text(encoding='utf8')); old['BUILD'] = build
init.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf8')
print('Updated PvP75 data, build', build)
