"""Map native hero-template creation to its actual captured PvP factory."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import proxy_reference
from verify_stages import sha
ROOT=hero.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('verification','negative','out'):ap.add_argument('--'+key,required=True)
    a=ap.parse_args();bundle=Path(a.verification).resolve();negative=Path(a.negative).resolve();evidence={}
    for key,path in (('regression',bundle/'summary.json'),('negative',negative/'summary.json')):
        report=json.loads(path.read_text(encoding='utf8'))
        if not report['passed']:raise ValueError('failed '+key)
        evidence[key]=dict(path=str(path),sha256=sha(path))
    for path,digest in json.loads((bundle/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('input drift '+path)
    entries=[]
    def add(path,cls,names,target,scope):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=tree.body
        if cls:nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            node=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
            entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,
                lines=[node.lineno,node.end_lineno],ast_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest(),typed_target=target,scope=scope))
    add(hero.TARGETS,'NativeTargets',('hero_proxy',),'HeroCombat::proxy',
        'Actual saved pre-admission factory; ordinary normal-mode native template, RNG restoration, private unregistered temporary, cache publication only after successful sync.')
    add(hero.TARGETS,'HeroProxy',('__init__','sync','__setitem__','update'),'HeroProxyState / HeroCombat proxy writes',
        'Full constructor shape and source metadata; HP/ash/status writes and all blocked conversion keys. Arbitrary unknown dictionary fields are not a supported typed boundary.')
    add(hero.REF/'modkit/pvp/native_patch.py','NativeCombatPatch',('__init__','_defaults','_install','_guard_boss_spawns'),
        'Captured ordinary factory specialization',
        'Reference executes actual installation and boss guard. Current PvP disconnects campaign/boss/random-pumpkin hooks before capturing this factory; ordinary kind is accepted.')
    add(proxy_reference.PATCH,None,('__pvz_sb_wrap_add_zombie','__pvz_sb_call_native_add_zombie','__pvz_sb_mark_i_zombie_zombie_placed_if_spawned'),
        'HeroCombat::proxy / populate_original_zombie',
        'Fixed ordinary name and normal mode: full source wrapper is exercised independently. Other summon kinds remain the separate production admission migration.')
    add(ROOT/'extract/original/functions.py',None,('新增僵尸',),'populate_original_zombie',
        'Independent comparison executes original shipped bytecode, including the temporary movement-speed RNG draw.')
    report=dict(schema=1,entries=entries,evidence=evidence,reference_dependencies={str(p):sha(p) for p in hero.PROXY_REFERENCE_PATHS},
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        retained_source_owns_proxy=True,live_position_identity=True,whole_battle_supported=False,full_branch_coverage=False,
        production_entry_switched=False,full_product_acceptance=False,
        pending=['Native loop consumers must use typed proxy write APIs','Production summon/card admission and lifecycle registration',
            'Remaining sourced hooks, bonus scan, main loop, AI, network, spectators and replay',
            'Old full suite, independent whole battles, formal PC/Android performance and final EXE/APK'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
