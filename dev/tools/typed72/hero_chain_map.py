"""Pin the hero chain's source ownership, tested scope and outstanding wiring."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REF=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verification',required=True);ap.add_argument('--sanitizer',required=True)
    ap.add_argument('--negative',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();evidence={}
    for label,path in (('release',a.verification),('asan',a.sanitizer),('negative_control',a.negative)):
        p=Path(path).resolve();r=json.loads((p/'summary.json').read_text(encoding='utf8'))
        if label!='negative_control' and not r['passed']:raise ValueError('verification failed: '+label)
        if label=='negative_control' and (r['passed'] or r['process_exit_code']!=0 or r['passed_cases']==r['cases']):raise ValueError('mutation not caught')
        if r['changed_inputs']:raise ValueError('verification input drift')
        evidence[label]=dict(path=str(p/'summary.json'),sha256=sha(p/'summary.json'),cases=r['cases'],passed_cases=r['passed_cases'],steps=r['compared_steps'])
        if label!='negative_control':
            pinned=json.loads((p/'pinned.json').read_text(encoding='utf8'))
            for name in ('hero.h','hero.cpp'):
                source=ROOT/'src/sim/typed'/name
                if pinned.get(str(source))!=sha(source):raise ValueError('changed hero implementation: '+name)
    specs=[
        (ROOT/'tools/pvp72_sources/native_targets.py','HeroProxy',('sync','__setitem__'),
         'HeroCombat::proxy/sync_proxies/write_proxy_hp/write_proxy_ash/write_proxy_status',
         'Known HP/ash/status fields only; full constructor collider and ordinary proxy fields remain pending.'),
        (ROOT/'tools/pvp72_sources/native_targets.py','NativeTargets',
         ('source','owner','source_id','context','_attack_key','damage_hero','_player_damage','hero_source_amount','tag_entity'),
         'HeroCombat / HeroContext','Typed hero selection, source resolution, damage, budgets, identity and projectile birth metadata.'),
        (ROOT/'tools/pvp72_sources/native_battle.py','NativeBattle',('_hero_damage_factor','_hero_damaged'),
         'HeroCombat::damage_factor/on_damage','Current hero rules and ordered damage events; transport consumers pending.'),
        (ROOT/'tools/pvp72_sources/zombie_secrets.py','ZombieSecrets',('hero_amount','_last_stand_step'),
         'HeroCombat::last_stand_amount/step_last_stand','Locked-deck secret IDs; full zombie-secret controller remains pending.'),
        (REF/'modkit/pvp/balance68006.py',None,('fire_color','hero_amount'),
         'balanced_hero_amount','Full source selection precedence.'),
    ]
    entries=[]
    for path,cls,names,target,scope in specs:
        source=path.read_text(encoding='utf8');tree=ast.parse(source,str(path))
        nodes=tree.body if cls is None else next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            n=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
            text='\n'.join(source.splitlines()[n.lineno-1:n.end_lineno])
            entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,
                lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),typed_target=target,scope=scope))
    dependencies=[ROOT/'src/sim/pvp/hand/misc.cpp',ROOT/'src/sim/pvp/gen/pm_native_targets.cpp',
                  ROOT/'src/sim/pvp/gen/pm_native_battle.cpp',ROOT/'src/sim/pvp/gen/pm_zombie_secrets.cpp',
                  ROOT/'src/sim/pvp/gen/pm_balance68006.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,implementation={str(ROOT/'src/sim/typed'/n):sha(ROOT/'src/sim/typed'/n) for n in ('hero.h','hero.cpp')},
        entries=entries,source_ownership_review={str(p):sha(p) for p in dependencies},evidence=evidence,
        original_hurt=dict(source=str(REF/'reverse_engineered/raw/pvzrouge.pyc'),first_line=197,bytecode_size=96,
            pvp_guard_change='Original bytes 0:2 replaced by JUMP_ABSOLUTE 8, as NativeTargets.install requires.'),
        full_product_acceptance=False,authoritative_world_integrated=False,full_branch_coverage=False,no_product_performance_claim=True,
        pending=['Complete HeroProxy constructor and remaining direct-write fields','Full projectile motion driver and collision integration (ownership/flight/splash separately verified)',
                 'Complete remaining sourced hooks and production lifecycle services; the actual synchronous death chain has separate evidence',
                 'Full hero physics, input, effects, render and world tick','AI/network/replay typed state integration',
                 'Full source/branch closure, full old suite, same-rule battle differential and final product gates'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
