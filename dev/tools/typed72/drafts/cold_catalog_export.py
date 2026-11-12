"""Build-time native catalog extraction; no Python dependency in the C++ room."""
import hashlib
import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
import proxy_reference

def load_catalog():
    proxy_reference.load()
    return importlib.import_module(proxy_reference.PACKAGE+'.catalog')

def cpp(value):
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,(int,float)):return repr(float(value))
    if isinstance(value,list):return '{'+','.join(cpp(v) for v in value)+'}'
    raise TypeError(type(value).__name__)

def generate(export,path):
    cards=export['raw_templates'];groups={name:[] for name in ('REQUIRED_STRINGS','REQUIRED_NUMBERS','REQUIRED_FLAGS','OPTIONAL_STRINGS','OPTIONAL_NUMBERS','OPTIONAL_FLAGS')}
    fields=defaultdict(list)
    for card in cards.values():
        for name,value in card.items():fields[name].append(value)
    for name in ('projectile_asset',):fields[name].append('')
    for name in ('slime_sticky','umbrella_secret','grenade_secret'):fields[name].append(False)
    for name,values in fields.items():
        if name in ('slow','targets','native_secret_names'):continue
        kinds={type(v) for v in values if v is not None}
        if kinds=={str}:kind='STRINGS'
        elif kinds=={bool}:kind='FLAGS'
        elif kinds<={int,float}:kind='NUMBERS'
        else:raise TypeError((name,kinds))
        required=len(values)==len(cards) and None not in values
        groups[('REQUIRED_' if required else 'OPTIONAL_')+kind].append(name)
    header=['// Generated from the initialized existing V/hand catalog. Do not edit.','#pragma once']
    for name,values in groups.items():header.append('#define PVZ72_COLD_'+name+'(X) '+' '.join('X('+v+')' for v in sorted(values)))
    (path/'cold_card_fields.h').write_text('\n'.join(header)+'\n',encoding='utf8')
    required=set(v for group,values in groups.items() if group.startswith('REQUIRED_') for v in values)
    code=['// Generated from a hash-pinned initialized V/hand export; no runtime V/JSON interpreter.',
          '#include "cold_catalog.h"','namespace pvz::typed72 {','const ColdCatalogData& compiled_cold_catalog(){',
          'static const ColdCatalogData data=[] { ColdCatalogData d;','d.cards.reserve('+str(len(cards))+');']
    for key in export['card_order']:
        card=cards[key];code.append('{ ColdCard c;')
        for name,value in card.items():
            if value is None:code.append('c.'+name+'.set_null();')
            elif name in required:code.append('c.'+name+'='+cpp(value)+';')
            elif name=='slow':code.append('c.slow.set(ColdNumber{'+cpp(value)+'});')
            else:code.append('c.'+name+'.set('+cpp(value)+');')
        code.append('d.cards.push_back(std::move(c)); }')
    for base,replacement in export['replacements'].items():
        code.append('d.replacements.push_back({'+','.join(cpp(v) for v in (base,replacement['secret'],replacement['resolved_id']))+'});')
    for name in ('derived_bases','costs','health','plant_cooldowns','zombie_cooldowns'):
        for key,value in export[name].items():code.append('d.'+name+'.emplace('+cpp(key)+','+cpp(value)+');')
    for name,source in (('protected_cards','protected'),('boss_names','boss_names'),('deathmatch_allowed_producers','deathmatch_allowed_producers')):
        code.append('d.'+name+'='+cpp(export[source])+';')
    for name,order in (('zombie_cost_set','COST_SET'),('zombie_cost_add','COST_ADD'),('zombie_hp_factor','HP_FACTOR')):
        for secret in export['zombie_order_'+order]:
            values=export[name][secret]
            if name=='zombie_hp_factor':values={target:values[0] for target in values[1]}
            code.append('d.'+name+'.push_back({'+cpp(secret)+',{'+','.join('{'+cpp(k)+','+cpp(v)+'}' for k,v in values.items())+'}});')
    for name in ('fast_plant_cooldown_factor','hardening_min_base_hp','hardening_hp_factor','starfruit_cost','sea_shroom_surcharge',
                 'imitate_cooldown_factor','rush_cooldown','imitate_secret','rage_torch_art','catalog_hash','rules_hash'):
        code.append('d.'+name+'='+cpp(export[name])+';')
    code+=['return d;}();return data;','}','} // namespace pvz::typed72']
    (path/'cold_catalog_data.cpp').write_text('\n'.join(code)+'\n',encoding='utf8')
    return groups

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--v-export',type=Path);args=ap.parse_args()
    catalog=load_catalog()
    rows=defaultdict(lambda:defaultdict(int))
    for card in catalog.CARDS.values():
        for key,value in card.items():rows[key][type(value).__name__]+=1
    out=ROOT/'test_results/cold-catalog-work'
    out.mkdir(parents=True,exist_ok=True)
    paths=proxy_reference.paths()+[Path(__file__).resolve()]
    schema=dict(cards=len(catalog.CARDS),catalog_sha256=catalog.catalog_hash(),fields=dict(rows),
                pinned={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (out/'schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'catalog.json').write_text(json.dumps(catalog.CARDS,ensure_ascii=False,indent=2),encoding='utf8')
    if args.v_export:
        raw=args.v_export.read_bytes();export=json.loads(raw)
        differences=[]
        for key in sorted(set(export['raw_templates'])|set(catalog.CARDS)):
            v,p=export['raw_templates'].get(key,{}),catalog.CARDS.get(key,{})
            for field in sorted(set(v)|set(p)):
                if field not in v or field not in p or v[field]!=p[field]:differences.append(dict(card=key,field=field,v=v.get(field),python=p.get(field),v_present=field in v,python_present=field in p))
        groups=generate(export,Path(__file__).resolve().parent)
        report=dict(v_export=str(args.v_export.resolve()),v_export_sha256=hashlib.sha256(raw).hexdigest(),
                    v_catalog_hash=export['catalog_hash'],python_catalog_hash=catalog.catalog_hash(),cards=len(export['raw_templates']),
                    differences=differences,groups=groups,generated={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('cold_card_fields.h','cold_catalog_data.cpp')})
        (out/'generation-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(dict(cards=report['cards'],differences=len(differences),v_catalog_hash=export['catalog_hash'],generated=report['generated'])))
    else:print(json.dumps(dict(cards=schema['cards'],fields=schema['fields']),ensure_ascii=True))

if __name__=='__main__':main()
