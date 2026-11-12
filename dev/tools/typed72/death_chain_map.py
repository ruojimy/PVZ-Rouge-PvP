"""Ownership and open integration boundaries of the synchronous death chain."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_death as reference
from verify_stages import sha
ROOT=reference.ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verification',required=True);ap.add_argument('--negative',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();evidence={}
    for key,directory in [('regression',a.verification),('negative',a.negative)]:
        p=Path(directory).resolve()/'summary.json';r=json.loads(p.read_text(encoding='utf8'))
        if not r['passed']:raise ValueError('unpassed '+key)
        evidence[key]=dict(path=str(p),sha256=sha(p))
    for path,digest in json.loads((Path(a.verification)/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('source drift '+path)
    entries=[]
    def add(path,names,target,scope,cls=None,nested=False):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=list(ast.walk(tree)) if nested else tree.body
        if cls:nodes=next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            matches=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(matches)!=1:raise ValueError('ambiguous source '+name)
            n=matches[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope,
                branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),full_branch_coverage=False))
    names=('wrap_damage_zombie','wrap_surface_damage_zombie','wrap_ash_zombie','maybe_trigger_chili_zombie_death',
        'maybe_trigger_doom_zombie_death','maybe_trigger_gravebuster_zombie_death','maybe_trigger_plant_zombie_death_effects','update_doom_zombie_auto_explode')
    add(reference.patch.PATCH,tuple(reference.P+n for n in names),'DamagePatch / NativeDeathChain',
        'Actual synchronous bodies and typed services. Preserves captured-object versus live-index death arguments, selector-local catches, 60-Hz age clock, raw native source fallback and marker-before-spawn order.')
    add(reference.doom.NATIVE_PATCH,('bind',),'SourcedContext / NativeDeathChain',
        'Literal sourced wrapper, applied to eight actual death/chili entry points. Full and default-fast paths tested; thirteen other bindings and the bonus scheduler remain open.',nested=True)
    add(reference.hero.TARGETS,('context_effects',),'HeroCombat::context_effects',
        'Exact fast-path net effect and proxy synchronization order, tested with missing fields, nested contexts and replaced hero positions.',cls='NativeTargets')
    owned=[ROOT/'src/sim/pvp/gen/pm_native_patch.cpp',ROOT/'src/sim/pvp/gen/pm_patch1501.cpp',ROOT/'src/sim/pvp/gen/pm_native_targets.cpp',
        ROOT/'src/sim/pvp/shim/pm_cppcore.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership_review={str(p):sha(p) for p in owned},implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        evidence=evidence,full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Complete bonus scan and remaining thirteen sourced hooks','Complete HeroProxy native template constructor and remaining writable fields',
            'Install production plant admission, omitted target registry and atlas/catalog',
            'Complete authoritative tick, all remaining mechanics, AI, multiplayer, spectators and replay',
            'Old full suite, source/branch closure, whole-battle comparison, formal PC/Android performance and final EXE/APK'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
