"""Source ownership for entity lifetime, projectile rules and ordered events."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_projectiles as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verification',required=True);ap.add_argument('--negative',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    regression=Path(a.verification).resolve();negative=Path(a.negative).resolve();evidence={}
    for name,folder in [('regression',regression),('negative',negative)]:
        report=json.loads((folder/'summary.json').read_text(encoding='utf8'))
        if not report['passed']:raise ValueError('unpassed '+name)
        evidence[name]={'path':str(folder/'summary.json'),'sha256':sha(folder/'summary.json')}
    for path,digest in json.loads((regression/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('input drift '+path)
    entries=[]
    def add(path,cls,names,target,scope):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path))
        nodes=tree.body if cls is None else next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            n=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
            entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope,
                branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),full_branch_coverage=False))
    add(reference.hero.TARGETS,'NativeTargets',('_new_entity','tag_entity'),'CombatRuntime::spawn / TypedBattleState::entity_born / HeroCombat::tag_entity',
        'Synchronous raw birth and ownership tagging; typed entity retained through source references and list replacements.')
    add(reference.hero.PROJECTILES,None,('begin_flight','fire_form'),'begin_flight / ProjectileFlight','Source-specific range initialization and fire-form identity.')
    add(reference.hero.PROJECTILES,'NativeProjectiles',('expired','cull_flight','head_geometry','head_overlaps_area','impact'),'ProjectileRules / EntityCollection',
        'Flight/range, mobile basketball targets, live-list culling, head geometry and splash. Main entity motion and zombie-pea seam wrapper pending.')
    add(reference.CONTENT,'NativeContent',('point','damage_target'),'ContentTargets / content_target_point / ProjectileRules::basketball',
        'Shared typed content damage; mobile unit coverage here, stationary plant/direct hero branches additionally covered by plant-chain evidence.')
    add(reference.FLYING,'FlyingPlants',('target_contact',),'ContentTargets::contact / flying_target_contact','Mobile body/head sweep and separately verified plant/hero branches; complete flying projectile update pending.')
    add(reference.SCALE,None,('factor','unit_root'),'CollisionCatalog / unit_root','Typed immutable fixture catalog; actual production atlas/catalog resolution pending.')
    add(reference.SIMULATION,None,('wrap_delta',),'wrap_delta','Same arithmetic order and half-width seam tie.')
    add(reference.patch.PATCH,None,tuple(reference.patch.PREFIX+n for n in ('plant_zombie_head_center','plant_zombie_head_radius','segment_hits_ellipse')),
        'plant_zombie_head / segment_hits_ellipse','Exact geometry with numeric typed positions and configuration.')
    owned=[ROOT/'src/sim/pvp/gen'/n for n in ('pm_native_projectiles.cpp','pm_pvp56_plants.cpp','pm_native_content.cpp','pm_native_scale.cpp','pm_patch1501.cpp')]
    owned += [ROOT/'src/sim/pvp/hand/misc.cpp',ROOT/'src/sim/pvp/hand/targeting72.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership={str(p):sha(p) for p in owned},
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},evidence=evidence,
        event_journal='One authoritative std::variant journal, preserving interleaved hero/relic/basketball/splash emissions.',
        whole_battle_supported=False,production_entry_switched=False,full_branch_coverage=False,full_product_acceptance=False,
        pending=['Full entity motion/torch/zombie-pea/flying-projectile driver','Production atlas and plant-zombie catalog loading',
            'Full synchronous death terrain/spawn effects and sourced PvP wrappers','E1 complete ordinary zombie/pea/hero tick and drawing',
            'All current mechanics, AI, networking/spectators/replay consumers','Full old suite and source/branch closure','Whole battle differential, formal PC/Android performance and products'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
