"""PvP75 new-card art: import the delivered pack once, then bake atlas entries.

  python tools/pvp75_assets.py import <pack dir>   copy runtime/native/icons + metadata into assets/pvp75_newcards
  python tools/pvp75_assets.py build               write extract/assets/_png/pvp75-*.png and index.json rows
  python tools/pvp75_assets.py check               fail when the atlas does not match the imported pack

Status variants use the original recolour helpers' exact pixel rules (纯换色 / 不纯换色 /
换黑白, see src/sim/gen/original_funcs.cpp). 盾卫僵尸 draws body -> head -> wooden shield,
so every drawn head pose is the head with that pose's shield composited in front.
"""
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/pvp75_newcards'
PNG = ROOT / 'extract/assets/_png'
INDEX = ROOT / 'extract/assets/index.json'
ICONS = ROOT / 'extract/data/texture_card_icons74.json'
MANIFEST = ROOT / 'tools/pvp75_assets.json'
PACK_FILES = ('README.md', 'INTEGRATION.md', 'REVISION_2.md', 'SHA256SUMS.txt', 'animations.json')
VARIANTS = (('-黑白', 'gray', None), ('-受伤', 'pure', (255, 255, 255)), ('-冰冻', 'impure', (0, 0, 255)),
            ('-灰烬', 'pure', (0, 0, 0)), ('-魅惑', 'impure', (128, 0, 128)))
CARDS = {'巴豆': 'plant:巴豆', '激光豆': 'plant:激光豆', '盾卫僵尸': 'zombie:盾卫僵尸'}
# Native-size card faces in the shipped 图片/ folder (the card renderer resolves 图片/<asset>.png first).
IMAGES = ROOT / 'build/Release/图片'
APP_IMAGES = ROOT / 'build/app-typed72-v2/Release/图片'  # the PC release stages this copy
FACES = {'巴豆.png': 'native/巴豆/巴豆.png', '激光豆.png': 'native/激光豆/激光豆.png',
         '盾卫僵尸.png': 'native/盾卫僵尸/盾卫僵尸.png', '盾卫僵尸-身.png': 'native/盾卫僵尸/盾卫僵尸-身.png'}


def faces():
    out = {name: (SRC / rel).read_bytes() for name, rel in FACES.items()}
    from PIL import Image
    head = Image.alpha_composite(Image.open(SRC / 'native/盾卫僵尸/盾卫僵尸-首.png').convert('RGBA'),
                                 Image.open(SRC / 'native/盾卫僵尸/盾卫僵尸-盾.png').convert('RGBA'))
    out['盾卫僵尸-首.png'] = encode(head)
    # 克苏鲁之仆: the first frame of the original NPC_5 sheet (20x32) as its card face.
    servant = Image.open(ROOT / 'extract/assets/terraria/NPC_5.png').convert('RGBA').crop((0, 0, 20, 32))
    out['克苏鲁之仆.png'] = encode(servant)
    return out


def recolor(image, mode, color):
    from PIL import Image  # noqa: F401  (build only; the gate below needs no PIL)
    out = image.copy(); px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if mode == 'gray':
                if r or g or b:
                    v = min(255, (r + g + b) // 3 + 60); px[x, y] = (v, v, v, a)
            elif mode == 'pure':
                if a > 100: px[x, y] = color + (255,)
            elif (r or g or b) and a > 100:
                px[x, y] = color + (255,)
    return out


def load(rel):
    from PIL import Image
    return Image.open(SRC / rel).convert('RGBA')


def over(*layers):
    from PIL import Image
    out = Image.new('RGBA', layers[0].size, (0, 0, 0, 0))
    for layer in layers: out = Image.alpha_composite(out, layer)
    return out


def sources():
    """atlas key -> (image, variants?) in a stable order."""
    rows = {}
    for folder in ('巴豆', '激光豆'):
        for p in sorted((SRC / 'runtime' / folder).glob('*.png')):
            rows[p.stem] = (load(p.relative_to(SRC)), True)
    for p in sorted((SRC / 'runtime/特效').glob('*.png')):
        if p.stem.endswith('-原图'): continue
        rows[p.stem] = (load(p.relative_to(SRC)), False)
    z = 'runtime/盾卫僵尸/'
    rows['盾卫僵尸'] = (load(z + '盾卫僵尸.png'), True)
    rows['盾卫僵尸-身'] = (load(z + '盾卫僵尸-身.png'), True)
    rows['盾卫僵尸-首'] = (over(load(z + '盾卫僵尸-首.png'), load(z + '盾卫僵尸-盾.png')), True)
    for n in range(4):
        pose = '盾卫僵尸-举盾%d' % n
        rows[pose] = (load(z + pose + '.png'), True)
        rows[pose + '-身'] = (load(z + pose + '-身.png'), True)
        rows[pose + '-首'] = (over(load(z + pose + '-首.png'), load(z + pose + '-盾.png')), True)
    for name in ('木盾牌', '木盾牌-正面', '木盾牌-侧面'):
        rows[name] = (load(z + name + '.png'), False)
    # 克苏鲁之仆 card face: the first NPC_5 frame, nearest-neighbour x2 (the world draws the sheet itself).
    from PIL import Image
    servant = Image.open(ROOT / 'extract/assets/terraria/NPC_5.png').convert('RGBA').crop((0, 0, 20, 32))
    rows['克苏鲁之仆'] = (servant.resize((40, 64), Image.NEAREST), False)
    out = {}
    for key, (image, variants) in rows.items():
        out[key] = image
        if variants:
            for suffix, mode, color in VARIANTS: out[key + suffix] = recolor(image, mode, color)
    return out


def encode(image):
    buf = io.BytesIO(); image.save(buf, 'PNG', optimize=True); return buf.getvalue()


def plan():
    rows = {}
    for key, image in sources().items():
        data = encode(image)
        rows[key] = ('pvp75-' + hashlib.sha256(data).hexdigest()[:16] + '.png', image.width, image.height, data)
    icons = {}
    for name in CARDS:
        data = (SRC / 'icons' / (name + '.png')).read_bytes()
        icons[name] = ('pvp75-icon-' + hashlib.sha256(data).hexdigest()[:16] + '.png', data)
    return rows, icons


def build(write):
    rows, icons = plan()
    index = json.loads(INDEX.read_text('utf8'))
    atlas = index['图集']
    changed = False
    for key, (file, w, h, data) in rows.items():
        if atlas.get(key) != [file, w, h]:
            changed = True
            if write: atlas[key] = [file, w, h]
        target = PNG / file
        if not target.exists() or target.read_bytes() != data:
            changed = True
            if write: target.write_bytes(data)
    icon_rows = json.loads(ICONS.read_text('utf8'))
    keep = [r for r in icon_rows if r.get('key') not in {'icon:' + n for n in CARDS}]
    # PvP76: every card drawn with this art (e.g. secret:聚能 / zsecret:守卫) is listed, like the icon baker does.
    exported = json.loads((ROOT / 'extract/data/catalog.json').read_text('utf8'))['CARDS']
    for name, (file, data) in icons.items():
        owners = [CARDS[name]] + sorted(k for k, c in exported.items() if k != CARDS[name] and c.get('asset', c.get('name')) == name)
        keep.append(dict(cards=owners, category='植物' if CARDS[name].startswith('plant:') else '僵尸',
                         file='extract/assets/_png/' + file, height=128, key='icon:' + name,
                         name=name + ' · 完整卡面图标', projectile=False, scope='icon', width=128))
        target = PNG / file
        if not target.exists() or target.read_bytes() != data:
            changed = True
            if write: target.write_bytes(data)
    keep.sort(key=lambda r: r['key'])
    if keep != icon_rows: changed = True
    for name, data in faces().items():
        for folder in (IMAGES, APP_IMAGES):
            if not folder.is_dir(): continue
            target = folder / name
            if not target.exists() or target.read_bytes() != data:
                changed = True
                if write: target.write_bytes(data)
    manifest = {key: rows[key][0] for key in rows} | {'icon:' + n: icons[n][0] for n in icons}
    manifest |= {'face:' + name: hashlib.sha256(data).hexdigest() for name, data in faces().items()}
    if write:
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), 'utf8')
        ICONS.write_text(json.dumps(keep, ensure_ascii=False, indent=1), 'utf8')
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', 'utf8')
    return changed, len(rows), len(icons)


def import_pack(pack):
    pack = Path(pack)
    sums = {}
    for line in (pack / 'SHA256SUMS.txt').read_text('utf8').splitlines():
        if line.strip():
            digest, _, name = line.partition('  '); sums[name.strip().lstrip('*').lstrip('./')] = digest.strip()
    copied = 0
    for sub in ('runtime', 'native', 'icons'):
        for p in sorted((pack / sub).rglob('*.png')):
            rel = p.relative_to(pack).as_posix()
            if rel in sums and hashlib.sha256(p.read_bytes()).hexdigest() != sums[rel]:
                raise SystemExit('checksum mismatch: ' + rel)
            dest = SRC / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest); copied += 1
    for name in PACK_FILES: shutil.copyfile(pack / name, SRC / name)
    print('imported', copied, 'images into', SRC)


def gate():
    """Build gate without PIL: every recorded row is in the atlas and its file exists."""
    manifest = json.loads(MANIFEST.read_text('utf8'))
    atlas = json.loads(INDEX.read_text('utf8'))['图集']
    icons = {r['key']: r['file'] for r in json.loads(ICONS.read_text('utf8'))}
    for key, file in manifest.items():
        if key.startswith('face:'):
            target = IMAGES / key[5:]
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != file: raise SystemExit('PvP75 card face missing: ' + key)
            continue
        if key.startswith('icon:'):
            if icons.get(key) != 'extract/assets/_png/' + file: raise SystemExit('PvP75 icon row missing: ' + key)
        elif not atlas.get(key) or atlas[key][0] != file: raise SystemExit('PvP75 atlas row missing: ' + key)
        if not (PNG / file).is_file(): raise SystemExit('PvP75 art file missing: ' + file)
    print('PvP75 assets: gate checked', len(manifest), 'rows')


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if command == '--check': gate(); raise SystemExit(0)
    if command == 'import': import_pack(sys.argv[2])
    elif command == 'build':
        changed, n, icons = build(True); print('PvP75 assets:', n, 'atlas rows,', icons, 'icons,', 'updated' if changed else 'unchanged')
    else:
        changed, n, icons = build(False)
        if changed: raise SystemExit('PvP75 assets are stale: run tools/pvp75_assets.py build')
        print('PvP75 assets: checked', n, 'atlas rows')
