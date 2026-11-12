"""Pin plant, terrain and content-target ownership without claiming a full tick."""
import argparse
import ast
import hashlib
import json
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_plants as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verification',required=True);ap.add_argument('--negative',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    evidence={}
    for key,directory in [('regression',a.verification),('negative',a.negative)]:
        p=Path(directory).resolve()/'summary.json';report=json.loads(p.read_text(encoding='utf8'))
        if not report['passed']:raise ValueError('unpassed evidence '+key)
        evidence[key]=dict(path=str(p),sha256=sha(p))
    for path,digest in json.loads((Path(a.verification)/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('implementation drift '+path)
    entries=[]
    def add(path,names,target,scope,cls=None,nested=False):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=list(ast.walk(tree)) if nested else tree.body
        if cls:nodes=next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            matches=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(matches)!=1:raise ValueError('ambiguous source '+name)
            n=matches[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,
                lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope,
                branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),full_branch_coverage=False))
    raw_names=('种植植物','清除植物','哪个植物','哪个无南瓜植物','摧毁方块','摧毁实方块','增加重要方块')
    add(reference.FUNCTIONS,raw_names,'plant_original / find_plant / clear_original_plant / destroy_original_block / OriginalPlantLifecycle',
        'Literal raw body, including partial constructor failure, RNG order and installed lifecycle callback dispatch. Oracle executes shipped bytecode; PvP/patch plant admission and registration remain pending.')
    add(reference.hero.BATTLE,('keep_bedrock',),'destroy_pvp_block','Exact native PvP bedrock wrapper, including wrapped guard lookup before strict raw bounds.',nested=True)
    names=('float','randint','sign','grid','tile_at','block_name','empty_block_names','chili_surface_overlay_names',
        'chili_has_plant_slot','is_chili_pass_through_block_name','is_chili_surface_overlay','is_chili_ground_block',
        'chili_fire_column','chili_cell_at','chili_lane_row_from_pos','chili_int_or_none','update_chili_zombie_row_hint',
        'gravebuster_zombie_cell','clear_gravebuster_grave_cell','place_grave_from_gravebuster_zombie',
        'spawn_gravebuster_plant_from_zombie','play_named_sound')
    add(reference.patch.PATCH,tuple(reference.patch.PREFIX+n for n in names),'WorldTerrain / GravebusterEffects / chili_lane_row / update_chili_row_hint',
        'Canonical record/null terrain and fixed typed fields. Full raw dynamic-input error branches and sourced PvP death wrapper composition are not closed.')
    add(reference.projectiles.CONTENT,('point','damage_target'),'ContentTargets::point / damage',
        'Stationary plant, mobile zombie and hero-proxy targets; typed protection and actual raw damage callbacks. Content kind and context preserved. Entire content controller remains pending.',cls='NativeContent')
    add(reference.projectiles.FLYING,('target_contact',),'ContentTargets::contact / flying_target_contact',
        'Plant .45-tile ellipse, mobile body/head geometry and cached hero position. Complete flying projectile driver remains pending.',cls='FlyingPlants')
    raw=marshal.loads(reference.hero.RAW.read_bytes());codes={c.co_name:c for c in raw.co_consts if isinstance(c,types.CodeType)}
    owners=[ROOT/'src/sim/gen/original_funcs.cpp',ROOT/'src/sim/pvp/gen/pm_patch1501.cpp',ROOT/'src/sim/pvp/gen/pm_native_content.cpp',
        ROOT/'src/sim/pvp/gen/pm_native_battle.cpp',ROOT/'src/sim/pvp/hand/misc.cpp',ROOT/'src/sim/pvp/hand/targeting72.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership={str(p):sha(p) for p in owners},
        raw_functions={n:dict(first_line=codes[n].co_firstlineno,bytecode_size=len(codes[n].co_code),marshal_sha256=hashlib.sha256(marshal.dumps(codes[n])).hexdigest()) for n in raw_names},
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},evidence=evidence,
        authoritative_plant_and_tile_records=True,per_tick_map_copy=False,world_tick_implemented=False,full_product_acceptance=False,full_branch_coverage=False,
        pending=['PvP/patch plant admission, constructor wrappers, registration and direct writable fields',
            'Production lifecycle/admission wiring; chili/doom and sourced synchronous death composition have separate evidence',
            'Remaining NativeContent controller, enemy collection, taunt/route targeting and projectile drivers',
            'Complete ordinary zombie/pea/hero tick, all current mechanics, AI, multiplayer and replay',
            'Full original suite, source/branch closure, whole-battle differential, formal PC/Android performance and products'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
