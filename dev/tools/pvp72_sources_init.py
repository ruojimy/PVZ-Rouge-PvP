"""One-time import of explicitly changed translation inputs, with provenance."""
import hashlib, json, shutil
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvp')
target = root / 'tools/pvp72_sources'
target.mkdir(exist_ok=True)
names = ('balance catalog native_content native_targets native_battle zombie_secrets '
         'pvp70_content pvp58_vines native_imitater room draft_advisor ui_data '
         'native_protection native_placement app userdata replay simulation '
         'zombie_secret_catalog pvp71_catalog pvp66_secrets native_september_content').split()
manifest = {}
for name in names:
    p = source / (name + '.py')
    q = target / p.name
    if q.exists():
        raise RuntimeError('Refusing to overwrite ' + str(q))
    shutil.copy2(str(p), str(q))
    manifest[name] = {'source': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
(target / 'provenance71.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Imported', len(manifest), 'read-only reference inputs to owned PvP72 generation sources')
