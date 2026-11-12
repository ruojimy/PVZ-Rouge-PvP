"""Source ownership and unclosed integration boundaries for doom effects."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_doom as reference
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
    def add(path,names,target,scope,nested=False):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=list(ast.walk(tree)) if nested else tree.body
        for name in names:
            matches=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
            if len(matches)!=1:raise ValueError('ambiguous source '+name)
            n=matches[0];entries.append(dict(source=str(path),source_sha256=sha(path),symbol=name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,scope=scope,
                branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),full_branch_coverage=False))
    names=('doom_zombie_world_point','chili_zombie_world_point','spawn_doom_zombie_visuals','doom_zombie_knock_player',
        'doom_zombie_destroy_blocks','spawn_doom_zombie_explosion','spawn_effect_entity','append_unique_sequence',
        'plant_world_point','squash_zombie_kill_plant','zombie_target_point','is_charmed_zombie','plant_zombie_head_center')
    add(reference.patch.PATCH,tuple(reference.P+n for n in names),'DoomEffects / CombatRuntime / FullTargetsScope',
        'Canonical typed records and required installed synchronous services. Preserves RNG, visuals, terrain and callback/list identity semantics; full dynamic input schemas and sourced wrapper binding remain unclosed.')
    add(reference.LEGACY,('_doom_targets',),'DoomEffects::ash_targets',
        'Installed PvP target body: allegiance captured once, plants killed through installed clear, live zombie identity re-resolved, no inherited plant double-hit rule.')
    add(reference.NATIVE_PATCH,('pvp_doom',),'DoomEffects::ash_targets / FullTargetsScope',
        'Actual full_targets wrapper extracted as literal AST; omitted target provider is a required typed service, not a production collector implementation.',nested=True)
    owned=[ROOT/'src/sim/pvp/gen/pm_native_patch.cpp',ROOT/'src/sim/pvp/gen/pm_legacy_fixes.cpp',ROOT/'src/sim/pvp/gen/pm_patch1501.cpp',
        ROOT/'src/sim/pvp/shim/pm_cppcore.cpp',ROOT/'src/sim/pvp/hand/misc.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership_review={str(p):sha(p) for p in owned},implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        evidence=evidence,full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Complete remaining sourced PvP hooks and actual omitted-target provider; synchronous death composition has separate evidence','Complete HeroProxy template constructor and writable fields',
            'Chili/fire effect bodies and auto-explosion timers','Complete main battle tick, mechanics, AI, multiplayer and replay',
            'Old full suite, full source/branch closure, whole-battle differential, formal performance and products'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
