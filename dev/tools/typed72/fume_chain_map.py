"""Literal fumeshroom, producer protection, source and legacy-view map."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_fume as reference
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
    names=('has_thunder_secret', 'fumeshroom_zombie_is_thunder', 'point_within_tiles', 'angle_from_points', 'fumeshroom_target_candidate', 'pick_fumeshroom_zombie_target', 'ray_hits_circle', 'damage_plant_from_fumeshroom', 'damage_player_from_fumeshroom', 'damage_zombie_from_fumeshroom', 'zombie_has_active_metal', 'apply_fumeshroom_thunder_stun', 'fumeshroom_zombie_fire_frames', 'fumeshroom_zombie_shoot_tick', 'spawn_fumeshroom_bubble_burst', 'fumeshroom_visual_tick', 'apply_fumeshroom_line_attack', 'update_fumeshroom_zombie_fire_animation', 'update_fumeshroom_zombie', 'update_fumeshroom_bubbles', 'play_zombie_pea_splat', 'plant_zombie_head_radius')
    add(reference.patch.PATCH,[reference.P+n for n in names],'FumeEffects / plant_zombie_head')
    add(reference.doom.NATIVE_PATCH,('bind',),'FumeEffects::update / line / SourcedContext',parent='bind_targets')
    add(reference.plants.protection.PROTECTION,('_patch_damage_code',),'FumeEffects::damage_plant / UnitProtection::amount')
    add(reference.doom.LEGACY,('_target_wrapper','_damage_wrapper'),'FumeEffects legacy I-Zombie guards and retained roster view')
    report=dict(schema=1,entries=entries,evidence=evidence,
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        semantics=['Native nearest-target order, directional cone and exact circle/ray margins.',
            'Numeric plant damage uses the actual producer/secret protection expression before clear callbacks.',
            'Zombie damage preserves captured numeric indices, then falls back to the retained record after callback failure.',
            'Unchanged player HP triggers the native direct-write fallback; I-Zombie direct-damage guard remains.',
            'Line attack snapshots recipients at the native phase boundary, including I-Zombie shallow-view list identity.',
            'Each due pulse invokes the bound sourced line before visuals, including multiple overdue pulses.',
            'Missing attack angle uses prior aim; None uses direction; metal stun checks post-damage equipment.',
            'Bubble creation uses no random draws; oldest overflow is discarded at 600; animation uses native 60 Hz time quantization.'],
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Other six sourced hooks and bonus scheduler','Complete original plant maintenance and PvP content scheduling',
            'Complete authoritative unit/entity/hero loops and custom content','AI/network/spectators/replay',
            'Old full suite, whole-battle comparisons, current Android validation, formal performance and game products'])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))
if __name__=='__main__':main()
