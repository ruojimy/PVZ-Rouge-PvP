"""Map record keys to typed fields from the probes' own read()/write() calls."""
import json,re,sys,collections
from pathlib import Path
root=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
P=root/'build/typed72-match-v1/probes';S=root/'build/typed72-integrated-v6/source/src/sim/typed'
gaps=collections.Counter()
for c in (root/'test_results/typed72-20261106/batch-r3').glob('*/comparison.json'):
    for k in json.loads(c.read_text(encoding='utf8')).get('field_gaps',{}):gaps[k]+=1
pat=re.compile(r'(?:read|write|read_point|write_point)\(\s*(?:\w+(?:\.\w+|\[[^\]]*\]|\.at\([^)]*\))*\s*,\s*)?"([^"]+)"\s*,\s*([^;]*?)\)\s*;')
pat2=re.compile(r'(?:write|write_point|read|read_point)\(\s*(?:\w+)\s*,\s*"([^"]+)"\s*,\s*([\w\.\->\*\[\]\(\)]+)\s*\)')
found=collections.defaultdict(collections.Counter)
for f in list(P.glob('*.cpp'))+list(P.glob('*.inc')):
    t=f.read_text(encoding='utf8',errors='replace')
    for k,v in pat2.findall(t):found[k][re.sub(r'\s','',v)]+=1
macros={}
for f in S.glob('*.h'):
    t=f.read_text(encoding='utf8',errors='replace')
    for name,key in re.findall(r'X\((\w+)\s*,\s*"([^"]+)"\)',t):macros.setdefault(key,(f.name,name))
# Keys are also usable from the hero/room/typed sources.
kinds=collections.defaultdict(list)
for k,n in gaps.items():
    m=re.match(r'only_in_(reference|typed):(\.[^.]+\.[^.]+|\.[^.]+)\.?(.*)',k)
    if not m:kinds['?'].append(k);continue
    kinds[m.group(1)+' '+m.group(2)].append((m.group(3),n))
for kind,items in kinds.items():
    print('==',kind,len(items))
    for item in sorted(items,key=lambda x:-x[1] if isinstance(x,tuple) else 0):
        if not isinstance(item,tuple):print('  ',item);continue
        key,n=item;base=key.split('.')[0]
        hit=found.get(base);mac=macros.get(base)
        print('  ',key,n,'->',(hit.most_common(2) if hit else ''),(mac or ''))
