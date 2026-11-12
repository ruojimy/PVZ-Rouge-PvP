"""Literal native lantern/healing source map, with remaining PvP66 work explicit."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_lantern as reference
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
    names=('remember_zombie_max_hp','track_zombie_max_hp','heal_zombie','heal_plant','light_therapy_multiplier',
        'point_in_square_radius','spawn_lantern_heal_effects','heal_lantern_zombie_targets','update_lantern_zombie',
        'update_native_lantern_charmed_healing','has_live_charmed_zombies')
    add(reference.patch.PATCH,[reference.P+n for n in names],'LanternEffects / DamagePatch::remember_max_hp')
    add(reference.doom.NATIVE_PATCH,('bind',),'LanternEffects::update / SourcedContext',parent='bind_targets')
    report=dict(schema=1,entries=entries,evidence=evidence,
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        semantics=['Specific maximum HP key wins even when None; missing and null remain distinct.',
            'Native zombie heal does not filter the dead key; plant heal does.',
            'HeroProxy rejects HP increases, while the helper still writes hurt and reports success.',
            'Visual offsets consume RNG before the fallible entity callback; captured list and new entity identity survive replacements.',
            'Native charmed healing captures the zombie roster before plant callbacks; each plant snapshots that retained roster anew.',
            'Sourced update preserves native secret selection and source tags, including all four owner seats.'],
        full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Other ten sourced hooks and bonus scheduler','PvP66 lantern burn/wake and complete original plant maintenance',
            'Complete authoritative unit/entity/hero loops and custom content','AI/network/spectators/replay',
            'Old full suite, whole-battle comparisons, current Android validation, formal performance and game products'])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))
if __name__=='__main__':main()
