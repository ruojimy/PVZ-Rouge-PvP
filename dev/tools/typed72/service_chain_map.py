"""Literal native umbrella and gold-magnet source map."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_services as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('verification','negative','out'):ap.add_argument('--'+name,required=True)
    a=ap.parse_args();folder=Path(a.verification).resolve();entries=[];evidence={}
    for name,path in (('regression',folder/'summary.json'),('negative',Path(a.negative).resolve()/'summary.json')):
        result=json.loads(path.read_text(encoding='utf8'))
        if not result['passed']:raise ValueError('failed '+name)
        evidence[name]=dict(path=str(path),sha256=sha(path))
    for path,digest in json.loads((folder/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('source drift '+path)
    def add(path,names,target,parent=None):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=tree.body
        if parent:
            selected=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==parent]
            if len(selected)!=1:raise ValueError('ambiguous owner '+parent)
            nodes=selected[0].body
        for name in names:
            selected=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(selected)!=1:raise ValueError('ambiguous symbol '+name)
            n=selected[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=name,owner=parent,
                lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target))
    names=('animate_service_plant_zombie_head', 'projectile_point', 'live_zombie', 'umbrella_reflect_projectiles', 'umbrella_bounce_basketballs', 'umbrella_knock_zombies', 'umbrella_knock_player', 'update_umbrella_zombie', 'zombie_has_head_armor', 'gold_magnet_target_point', 'spawn_magnet_attract_effect', 'pick_gold_magnet_bucket_target', 'gift_bucket_to_zombie', 'pick_gold_magnet_absorb_target', 'absorb_metal_from_zombie', 'update_gold_magnet_zombie', 'plant_zombie_hp_multiplier', 'scaled_plant_zombie_hp')
    add(reference.patch.PATCH,[reference.P+n for n in names],'ServicePlants')
    add(reference.doom.NATIVE_PATCH,('bind',),'ServicePlants::umbrella / magnet / SourcedContext',parent='bind_targets')
    add(reference.PVP70,('update_umbrella',),'ServicePlants::raw_pvp_umbrella',parent='_install')
    report=dict(schema=1,entries=entries,evidence=evidence,
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        semantics=['Reflection identity belongs to the actual unit; same-source repeats are skipped.',
            'Exact native sign treats zero as positive; tiny projectile velocity uses the fixed 120-unit fallback.',
            'Uncharmed umbrella can knock uncharmed units; charmed umbrella skips charmed units.',
            'PvP70 initial cooldown scaling runs before the sourced wrapper, including failing context entry.',
            'Gold-magnet target ties preserve list order, heroes cannot receive buckets, and handheld metal wins.',
            'Gift HP uses the native mode multiplier; effect callback failure retains prior armor removal.',
            'Attraction retains the pre-callback entity-list identity and tags the actual returned record.'],
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Other eight sourced hooks and bonus scheduler','Complete original plant maintenance and PvP content scheduling',
            'Complete authoritative unit/entity/hero loops and custom content','AI/network/spectators/replay',
            'Old full suite, whole-battle comparisons, current Android validation, formal performance and game products'])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))
if __name__=='__main__':main()
