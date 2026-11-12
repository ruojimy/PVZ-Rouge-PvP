"""Offline cold-data corpus for headless AI matches (docs/ai-nn).

    python build/ai-nn/export_corpus.py <decks.json from deck73_corpus> <out dir> [jobs]

For every scenario: cold73_export -> cold.json, atlas.bin(.draw.json/.recipes.json). The atlas
pixels and recipes are map/deck independent: one shared copy is kept (verified by SHA256 for every
export) and compressed; per scenario only cold.json and the draw-atlas JSON are kept, gzip'd,
with the draw JSON deduplicated by hash. Writes index.json describing every entry."""
import gzip, hashlib, json, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / 'build/pvp73-tools/build/Release/cold73_export.exe'
scen = json.loads(Path(sys.argv[1]).read_text('utf-8'))
out = Path(sys.argv[2]); jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 6
assert not out.exists(), out
(out / 'cold').mkdir(parents=True); (out / 'draw').mkdir()
sha = lambda b: hashlib.sha256(b).hexdigest()
work = Path(tempfile.mkdtemp(prefix='coldcorpus-'))

def one(i):
    sc = {k: v for k, v in scen[i].items() if k in ('map', 'seed', 'night', 'decks')}
    d = work / ('%03d' % i); d.mkdir()
    (d / 'sc.json').write_text(json.dumps(sc, ensure_ascii=False), encoding='utf-8')
    r = subprocess.run([str(EXPORT), str(d / 'sc.json'), str(d / 'cold.json'), str(d / 'atlas.bin')], cwd=str(ROOT),
                       capture_output=True, timeout=600)
    if r.returncode or not (d / 'cold.json').exists():
        return i, None, r.stderr.decode('utf-8', 'replace')[-400:]
    return i, d, ''

atlas_hash = recipes_hash = None; index = []; draws = {}
with ThreadPoolExecutor(jobs) as ex:
    for i, d, err in ex.map(one, range(len(scen))):
        sc = scen[i]; eid = '%03d' % i
        if d is None:
            print('FAIL', eid, err); index.append(dict(id=eid, scenario=sc, error=err)); continue
        a = sha((d / 'atlas.bin').read_bytes()); r = sha((d / 'atlas.bin.recipes.json').read_bytes())
        if atlas_hash is None:
            atlas_hash, recipes_hash = a, r
            with gzip.open(out / 'atlas.bin.gz', 'wb', 9) as f: f.write((d / 'atlas.bin').read_bytes())
            with gzip.open(out / 'atlas.bin.recipes.json.gz', 'wb', 9) as f: f.write((d / 'atlas.bin.recipes.json').read_bytes())
        assert (a, r) == (atlas_hash, recipes_hash), ('atlas differs', eid)
        cold = (d / 'cold.json').read_bytes(); draw = (d / 'atlas.bin.draw.json').read_bytes(); dh = sha(draw)
        if dh not in draws:
            draws[dh] = 'draw/%s.json.gz' % dh[:16]
            with gzip.open(out / draws[dh], 'wb', 9) as f: f.write(draw)
        with gzip.open(out / 'cold' / (eid + '.json.gz'), 'wb', 9) as f: f.write(cold)
        index.append(dict(id=eid, map=sc['map'], night=sc['night'], seed=sc['seed'], bans=sc.get('bans', []), decks=sc['decks'],
                          cold='cold/%s.json.gz' % eid, cold_sha256=sha(cold), draw=draws[dh], draw_sha256=dh))
        shutil.rmtree(d)
shutil.rmtree(work, ignore_errors=True)
data_version = json.loads((ROOT / 'extract/data/__init__.json').read_text('utf-8'))
meta = dict(exporter='build/pvp73-tools/cold73_export.cpp', exporter_sha256=sha(EXPORT.read_bytes()), data_init=data_version,
            atlas='atlas.bin.gz', atlas_sha256=atlas_hash, recipes='atlas.bin.recipes.json.gz', recipes_sha256=recipes_hash,
            note='atlas/recipes identical for every entry (checked); draw JSON deduplicated by hash; hashes are of uncompressed bytes',
            entries=index)
(out / 'index.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
print('entries', len(index), 'failed', sum('error' in e for e in index), 'draw files', len(draws))
