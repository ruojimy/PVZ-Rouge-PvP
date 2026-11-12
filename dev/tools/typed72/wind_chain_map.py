"""Record literal wind-chain ownership and the remaining driver obligations."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_wind as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('verification','negative','out'):ap.add_argument('--'+name,required=True)
    a=ap.parse_args();folder=Path(a.verification).resolve();entries=[];evidence={}
    for name,path in (('regression',folder/'summary.json'),('negative',Path(a.negative).resolve()/'summary.json')):
        r=json.loads(path.read_text(encoding='utf8'))
        if not r['passed']:raise ValueError('failed '+name)
        evidence[name]=dict(path=str(path),sha256=sha(path))
    for path,digest in json.loads((folder/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('source drift '+path)
    def add(path,names,target,parent=None,cls=None):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path))
        if cls:
            owners=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls]
            if len(owners)!=1:raise ValueError('class ambiguity')
            nodes=owners[0].body
        elif parent:
            owners=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==parent]
            if len(owners)!=1:raise ValueError('method ambiguity')
            nodes=owners[0].body
        else:nodes=tree.body
        for name in names:
            selected=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(selected)!=1:raise ValueError('symbol ambiguity '+name)
            n=selected[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=name,owner=cls or parent,
                lines=[n.lineno,n.end_lineno],ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target))
    add(reference.patch.PATCH,[reference.P+n for n in ('directed_velocity_limit','blover_side_match','apply_blover_zombie_wind','update_blover_zombie')],
        'WindEffects::raw_wind / raw_update')
    add(reference.WIND,('__init__','_cap','_accel','_push','_clovers','before_plants','after_plants','_after_plants_seat','blover_wind','after_zombies'),
        'WindEffects::radius_wind / before_plants / after_plants / after_zombies',cls='Wind')
    add(reference.projectiles.FLYING,('zombie_wind',),'WindEffects::wind (hidden flying entity view)',parent='install_wind')
    add(reference.PVP70,('zombie_wind',),'WindEffects::wind (bone/grenade extension)',parent='_install')
    add(reference.doom.NATIVE_PATCH,('bind',),'WindEffects::update / SourcedContext',parent='bind_targets')
    report=dict(schema=1,evidence=evidence,entries=entries,
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        position_storage='Native unit/entity positions own retainable typed Motion records. Dictionary replacement creates a new record; captured positions and aliases retain the old record.',
        ordering='PvP70 -> FlyingPlants hidden projectiles -> PvP59 radius/index mapping -> original patch. Temporary list identities and numeric callback mapping restore across nested calls and exceptions.',
        scope='Native and PvP wind bodies plus phase callbacks, composed with actual sourced hero context and damage/death dispatch; not the complete game driver.',
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Remaining eleven sourced hooks and bonus scheduling','Original plant wind branch and complete unit/entity/hero loops',
            'Custom projectile movement, admission and production content wiring','AI/network/spectators/replay','Old full suite, whole battles, formal PC/Android performance and products'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
