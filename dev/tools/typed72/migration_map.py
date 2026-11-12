"""Bind verified typed stages to original code identities without claiming PvP completion."""
import argparse
import hashlib
import json
import marshal
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/reverse_engineered/raw/pvzrouge.pyc'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verification',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();verification=Path(args.verification).resolve();out=Path(args.out)
    result=json.loads((verification/'summary.json').read_text(encoding='utf8'))
    pinned=json.loads((verification/'pinned.json').read_text(encoding='utf8'))
    if not result['passed']:raise ValueError('Verification did not pass')
    raw=RAW.read_bytes();root=marshal.loads(raw)
    functions={c.co_name:c for c in root.co_consts if isinstance(c,types.CodeType)}
    mappings=[
        ('original_damage','damage.cpp',['伤害僵尸','表面伤害僵尸'],[],
         ['native_targets._unit_damage / damage packets','patch1501 damage wrappers',
          'PvP72 damage/armor modifiers and heroes']),
        ('original_six_shooters','shooter.cpp',[],[(128324,130014)],
         ['plant maintenance / sleep / gate','PvP star override','projectile construction patches']),
        ('original_particles','particles.cpp',['增粒子','无墙位移处理'],[(108808,109352)],
         ['production atlas conversion','render event integration','PvP particle overrides']),
        ('body_displacement','physics.cpp',['位移处理'],[],
         ['hero/environment driver','PvP physics wrappers and special bodies']),
        ('periodic_flood','flood.cpp',[],[],
         ['world terrain ownership','tracking caller / target contexts','production boundary integration'])]
    entries=[]
    for name,cpp,names,ranges,pending in mappings:
        path=ROOT/'src/sim/typed'/cpp
        if pinned.get(str(path))!=sha(path):raise ValueError('Changed implementation: '+str(path))
        sources=[]
        for function in names:
            code=functions[function]
            sources.append(dict(kind='original_function_code_object',source=str(RAW),source_sha256=sha(RAW),
                code_object=function,code_sha256=hashlib.sha256(code.co_code).hexdigest(),
                code_object_offsets=[0,len(code.co_code)],root_module_offsets=None))
        for start,end in ranges:
            sources.append(dict(kind='raw_module_region',source=str(RAW),source_sha256=sha(RAW),
                code_object='<module>',offsets=[start,end],code_sha256=hashlib.sha256(root.co_code[start:end]).hexdigest()))
        if name=='periodic_flood':
            p=RAW.parents[2]/'modkit/pvp/native_flood.py'
            sources.append(dict(kind='PvP_source_function',source=str(p),source_sha256=sha(p),function='advance'))
        entries.append(dict(id=name,implementation=str(path.relative_to(ROOT)),sha256=sha(path),sources=sources,
            stage_status='differentially_verified_in_explicit_stage_scope',full_PvP72_status='not_integrated',
            pending_effective_rule_layers=pending,evidence=str(verification/'summary.json')))
    branch_rows=[]
    counts=result.get('branch_outcomes',[])
    for index in list(range(19))+list(range(32,40)):
        false_count=counts[index*2] if index*2<len(counts) else 0
        true_count=counts[index*2+1] if index*2+1<len(counts) else 0
        branch_rows.append(dict(id=index,false_count=false_count,true_count=true_count,
            outcome_coverage='both' if false_count and true_count else 'one_or_zero'))
    report=dict(schema=1,entries=entries,selected_instrumented_conditions=branch_rows,
        branch_coverage_scope='Only explicitly instrumented damage/shooter conditions; not all source branches or state combinations.',
        stage_count=len(entries),full_product_acceptance=False,full_tick_supported=False,
        authoritative_PvP72_world_migrated=False,remaining_legacy_world='src/sim/pyrt.h::Match / V',
        no_performance_claim=True,verification_sha256=sha(verification/'summary.json'))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(stage_count=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
