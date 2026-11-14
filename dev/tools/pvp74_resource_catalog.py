"""Inventory every shipped drawable, retaining exact original canvas dimensions."""
from pathlib import Path
import json, struct, hashlib
ROOT=Path(__file__).resolve().parents[1]
index=json.loads((ROOT/'extract/assets/index.json').read_text('utf8'))
cards=json.loads((ROOT/'extract/data/catalog.json').read_text('utf8'))['CARDS']
entries=[]
prefixes={'图集':'world','ui图集':'ui','背景图集':'bg','近景图集':'near','_globals':'global'}
shot_words=('弹','豌豆','孢子','星星','西瓜','篮球','玉米粒','黄油','冰球','芦笋','芜菁','火球','投掷','毒镖','回旋镖','冰瓜')
plant_terms={c['name'] for c in cards.values() if c['side']=='plant' and c['category']=='plant'}
def is_projectile(name):
    if not any(t in name for t in shot_words):return False
    if any(t in name for t in plant_terms) and not any(t in name for t in ('子弹','炮弹','弹幕')):return False
    return True
def add(key,name,file,w,h,scope):
    related=[]
    for ident,c in cards.items():
        terms={c.get('asset',''),c.get('native_name',''),c['name']}
        terms={t for t in terms if isinstance(t,str) and t}
        if any(t in name for t in terms):related.append(ident)
    category='界面' if scope=='ui' else '场景' if scope in ('bg','near','global') else '其他'
    if is_projectile(name):category='弹幕'
    if related:category='僵尸' if cards[related[0]]['side']=='zombie' else '植物'
    entries.append(dict(key=key,name=name,file=file,width=w,height=h,scope=scope,category=category,cards=related,projectile=is_projectile(name)))
for atlas,rows in index.items():
    if not isinstance(rows,dict):continue
    for name,row in rows.items():
        if isinstance(row,list) and len(row)==3 and isinstance(row[0],str) and row[0].endswith('.png'):
            add(prefixes.get(atlas,atlas)+':'+name,name,'extract/assets/_png/'+row[0],int(row[1]),int(row[2]),prefixes.get(atlas,atlas))
# Original sheets, card artwork, additional content art and bundled map art.
seen=set()
for directory in (ROOT/'build/Release/图片',ROOT/'extract/data/pvp/assets'):
    for p in sorted(directory.rglob('*.png')):
        data=p.read_bytes()
        if data[:8]!=b'\x89PNG\r\n\x1a\n':continue
        w,h=struct.unpack('>II',data[16:24])
        file=('图片/'+p.relative_to(directory).as_posix()) if directory.name=='图片' else p.relative_to(ROOT).as_posix()
        key='raw:'+file
        if key in seen:continue
        seen.add(key);add(key,p.stem,file,w,h,'raw')
entries.sort(key=lambda x:(x['name'],x['key']))
icons=ROOT/'extract/data/texture_card_icons74.json'
if icons.exists():entries.extend(json.loads(icons.read_text('utf8')))
# Composite cards expose the actual component sprites as well as their complete icon.
petrified_cards={ident for ident,c in cards.items()
                 if any('石化火炬' in (c.get(field) or '') for field in ('name','asset'))}
# Alias cards such as Rage use the existing blue flame frames and the raw stump
# input consumed by NativeArt.petrified_torch; their icon remains independent.
petrified_inputs={'world:蓝火炬1','world:蓝火炬2','world:蓝火炬3','raw:图片/火炬树桩-秃.png'}
for e in entries:
    for ident,c in cards.items():
        if ('墓碑' in c['name'] and any(p in e['name'] for p in ('坟墓','脑子','鸭圈'))
            or '石化火炬' in c['name'] and any(p in e['name'] for p in ('火炬','烧焦','树桩'))
            or ident in petrified_cards and e['key'] in petrified_inputs):
            if ident not in e['cards']:e['cards'].append(ident)
# Grass and stone terrain remain built-in, including old pack aliases.
excluded_cards={k for k,c in cards.items() if c['name'] in ('草坪','石块')}
excluded_roots={'草','土','石','石块'}
def root_name(e):return e['name'].split(' · ')[0].split('-')[0]
excluded=[e['key'] for e in entries if root_name(e) in excluded_roots]
entries=[e for e in entries if e['key'] not in set(excluded)]
heroes=[dict(id='hero:plant',name='植物戴夫',asset='疯狂戴夫'),dict(id='hero:zombie',name='僵尸戴夫',asset='僵尸戴夫')]
for e in entries:
    e['cards']=[k for k in e['cards'] if k not in excluded_cards]
    root=root_name(e)
    e['heroes']=['hero:plant'] if root in ('疯狂戴夫','大佬戴夫') else ['hero:zombie'] if root=='僵尸戴夫' else []
    if e['heroes']:e['category']='英雄'
entries.sort(key=lambda x:(x['name'],x['key']))
body={'schema':1,'entries':entries,'cards':[dict(id=k,name=c['name'],side=c['side'],category=c['category'],asset=c.get('asset',c['name'])) for k,c in cards.items() if k not in excluded_cards],'heroes':heroes,'excluded_resources':excluded,
      'atlas_sha256':hashlib.sha256((ROOT/'extract/assets/index.json').read_bytes()).hexdigest()}
target=ROOT/'extract/data/texture_resources74.json'
target.write_text(json.dumps(body,ensure_ascii=False,separators=(',',':')),'utf8')
print(json.dumps({'resources':len(entries),'cards':len(body['cards']),'heroes':len(heroes),'excluded':len(excluded),'file':str(target)},ensure_ascii=False))
