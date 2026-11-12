"""Literal squash, ballistic, legacy, sourced and PvP66 splash map."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_squash as reference
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
    names=('squash_zombie_origin','squash_zombie_candidate','pick_squash_zombie_target','squash_zombie_target_record','squash_zombie_ballistic_target','squash_zombie_target_velocity','play_squash_zombie_sound','spawn_squash_zombie_entity','update_squash_zombie','zombie_velocity','pick_target','solve_intercept','current_target_from_index','compute_solution','pick_squash_target','squash_target_from_lock','apply_squash_solution','patch_squash_entity','finish_squash_entities','is_enemy_squash_zombie_entity','has_pending_enemy_squash_zombie_entity','target_from_record','resolve_squash_zombie_target','squash_zombie_kill_plant','squash_zombie_damage_charmed_zombie','squash_zombie_damage_player','apply_squash_zombie_hit','update_squash_zombie_entities','len2','sign','plant_world_point','zombie_target_point')
    add(reference.patch.PATCH,[reference.P+n for n in names],'SquashEffects / NativeBallistics / PlantZombieTargeting')
    add(reference.doom.NATIVE_PATCH,('bind',),'SquashEffects::spawn / update / hit / SourcedContext',parent='bind_targets')
    add(reference.doom.LEGACY,('_target_wrapper','_damage_wrapper'),'SquashEffects legacy I-Zombie guards')
    add(reference.doom.LEGACY,('resolve',),'SquashEffects::resolve',parent='install')
    add(reference.PVP66,('wrap_delta',),'SquashEffects::splash_secret')
    tree=ast.parse(reference.PVP66.read_text(encoding='utf8'),str(reference.PVP66))
    method=[m for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='PlantSecrets66' for m in c.body if isinstance(m,ast.FunctionDef) and m.name=='squash']
    assert len(method)==1
    n=method[0];entries.append(dict(source=str(reference.PVP66),source_sha256=sha(reference.PVP66),symbol='squash',owner='PlantSecrets66',lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target='SquashEffects::splash_secret'))
    report=dict(schema=1,entries=entries,evidence=evidence,
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        semantics=['Source target precedence and strict candidate ties, including dead-but-positive records.',
            'World-owned velocity observations and exact native bracket/bisection order; first-root exit is equivalent to minimum-root selection.',
            'Early and late ballistic locks distinguish missing, None, empty and armed fields.',
            'Birth callbacks retain the original entity-list identity; current source charm is read after the callback.',
            'Damage resolves recorded identities again, preserves numeric callback indices and each exception fallback.',
            'Native I-Zombie guards and all three sourced entry wrappers remain in the chain.',
            'Enemy entity timing and once-only hit markers retain native frame semantics.',
            'PvP66 pressure splash uses ring distance, ordered live references and the shared typed event journal.'],
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Other three sourced hooks and bonus scheduler','Complete original plant maintenance and PvP content scheduling',
            'Complete authoritative unit/entity/hero loops and custom content','AI/network/spectators/replay',
            'Old full suite, whole-battle comparisons, current Android validation, formal performance and game products'])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))
if __name__=='__main__':main()
