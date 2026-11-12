"""Source ownership and explicit scope of typed native plant-zombie aiming."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_aim as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('verification','negative','out'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();folder=Path(a.verification).resolve();evidence={}
    for key,directory in (('regression',folder),('negative',Path(a.negative).resolve())):
        path=directory/'summary.json';r=json.loads(path.read_text(encoding='utf8'))
        if not r['passed']:raise ValueError('failed '+key)
        evidence[key]=dict(path=str(path),sha256=sha(path))
    for path,digest in json.loads((folder/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('source drift '+path)
    entries=[]
    def add(path,names,target,scope,nested=False):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=list(ast.walk(tree)) if nested else tree.body
        for name in names:
            matches=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(matches)!=1:raise ValueError('source ambiguity '+name)
            n=matches[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope))
    names=('plant_world_point','plant_zombie_aim_point','plant_zombie_head_center','direction_angle','direction_angle_diff','angle_in_direction',
        'sync_plant_zombie_head_angle','zombie_target_point','pick_charmed_plant_zombie_target','pick_enemy_charmed_zombie_target',
        'pick_plant_zombie_target','plant_zombie_target_point','update_plant_zombie_target')
    add(reference.plants.patch.PATCH,tuple(reference.P+n for n in names),'PlantZombieTargeting / shared native head geometry',
        'Actual ordered targeting for admitted native records. Full catalog, strict score ties, 90-degree cone, charm presence, target retention, live point resolution and zombie death-marker non-filtering.')
    add(reference.NATIVE_PATCH,('bind',),'PlantZombieTargeting::update / SourcedContext',
        'Actual non-fast sourced wrapper around update_plant_zombie_target, with all four owner seats and hero fallback.',True)
    add(reference.hero.REF/'modkit/pvp/legacy_fixes.py',('_is_i_zombie','_target_wrapper'),
        'PlantZombieTargeting::pick','I-Z excludes the allied native player; sourced PvP establishes normal mode before selection.')
    catalog=ROOT/'test_results/typed72-20261105/plant-zombie-catalog-generation/manifest.json'
    report=dict(schema=1,entries=entries,evidence=evidence,catalog_generation=dict(path=str(catalog),sha256=sha(catalog)),
        catalog_kinds=13,catalog_fields=33,catalog_test='aim-catalog compares every typed field against the actual installed patch namespace',
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        optimized='No temporary candidate-list copies: the typed selector calls only pure geometry helpers, so it cannot mutate the ordered rosters during the scan.',
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Other twelve sourced hooks, shooting/bonus scheduler and unit/hero/entity main loops','Production placement/registration and atlas/catalog consumers',
            'AI/network/spectators/replay','Old full suite, whole-battle comparisons, current Android checks and formal product performance'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
