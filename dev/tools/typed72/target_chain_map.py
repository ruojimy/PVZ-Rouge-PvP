"""Current target/identity/constructor chain ownership with explicit gaps."""
import argparse
import ast
import hashlib
import json
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
import verify_heroes as hero
import verify_patch as patch
ROOT=hero.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verification',required=True);ap.add_argument('--negative',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();folder=Path(a.verification).resolve();r=json.loads((folder/'summary.json').read_text(encoding='utf8'))
    negative=Path(a.negative).resolve();nr=json.loads((negative/'summary.json').read_text(encoding='utf8'))
    if not r['passed'] or not nr['passed']:raise ValueError('unpassed chain evidence')
    pinned=json.loads((folder/'pinned.json').read_text(encoding='utf8'))
    for path,digest in pinned.items():
        if sha(Path(path))!=digest:raise ValueError('changed implementation: '+path)
    entries=[]
    def add(path,cls,names,target,scope):
        text=path.read_text(encoding='utf8');tree=ast.parse(text,str(path))
        nodes=tree.body if cls is None else next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            n=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
            entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope,
                branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),branch_coverage_claim=False))
    add(hero.TARGETS,'NativeTargets',('_new_entity','tag_entity','full_targets','_zombie_damage','_surface_damage','_unit_damage','_shielded_damage','_record_melon_hit','_ash_damage'),
        'HeroCombat::tag_entity / FullTargetsScope / TargetDamage','Typed source/target ownership, packet guards and original raw callbacks; full battle scheduling pending.')
    add(hero.PROJECTILES,None,('fire_form','begin_flight'),'begin_flight / ProjectileFlight','Birth metadata; flight progression/culling/splash now have separate projectile-chain evidence. Full entity motion and torch callbacks pending.')
    names=('wrap_damage_zombie','wrap_surface_damage_zombie','wrap_ash_zombie','wrap_knockback_zombie','is_charmed_zombie',
        'is_gravebuster_zombie','has_charm_secret','zombie_bite_damage','charm_bite_pair_from_frame','adjust_charm_bite_damage',
        'is_enemy_squash_zombie_entity','native_enemy_squash_entity_from_caller','is_native_chili_ash_call','remember_zombie_max_hp',
        'pumpkin_armor_should_sound','play_pumpkin_armor_sound','maybe_trigger_chili_zombie_death','maybe_trigger_doom_zombie_death',
        'maybe_trigger_gravebuster_zombie_death','maybe_trigger_plant_zombie_death_effects')
    add(patch.PATCH,None,tuple(patch.PREFIX+n for n in names),'DamagePatch / NativeDamageOrigin',
        'Literal wrapper/selection rules. Direct-call frame gates tested as explicit fixtures. Actual loop call-site wiring, sourced PvP death contexts and terrain/spawn effect bodies NOT claimed.')
    add(ROOT/'extract/original/functions.py',None,('新增僵尸','击退僵尸'),'populate_original_zombie / DamagePatch::knockback',
        'All raw constructor kinds/modes and raw knockback. Independent oracle executes raw shipped bytecode. Patch/PvP constructor composition pending.')
    raw=marshal.loads(hero.RAW.read_bytes());codes={c.co_name:c for c in raw.co_consts if isinstance(c,types.CodeType)}
    owned=[ROOT/'src/sim/pvp/gen/pm_native_targets.cpp',ROOT/'src/sim/pvp/gen/pm_native_projectiles.cpp',
        ROOT/'src/sim/pvp/gen/pm_patch1501.cpp',ROOT/'src/sim/gen/original_funcs.cpp',ROOT/'src/sim/pvp/hand/misc.cpp',
        ROOT/'src/sim/pvp/pvprt.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership={str(p):sha(p) for p in owned},
        raw_functions={name:dict(first_line=codes[name].co_firstlineno,bytecode_size=len(codes[name].co_code),
            marshal_sha256=hashlib.sha256(marshal.dumps(codes[name])).hexdigest()) for name in ('新增僵尸','击退僵尸','伤害僵尸','表面伤害僵尸','灰烬僵尸')},
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        evidence=dict(regression=str(folder/'summary.json'),regression_sha256=sha(folder/'summary.json'),negative=str(negative/'summary.json'),negative_sha256=sha(negative/'summary.json')),
        single_unit_storage=True,world_tick_implemented=False,production_entry_switched=False,full_branch_coverage=False,full_product_acceptance=False,
        pending=['Full entity motion/collision driver and production atlas/catalog loading','Remaining sourced hooks and production lifecycle services; synchronous death composition has separate evidence',
            'Full HeroProxy constructor and direct writable collision fields','Patch and PvP constructor/admission/registration chain',
            'E1 complete ordinary zombie/pea/hero tick and drawing','All current PvP72 mechanics, AI, networking, spectators and replay',
            'Full old suite, full source/branch closure, independent whole-battle comparison, formal PC/Android performance and deliverables'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
