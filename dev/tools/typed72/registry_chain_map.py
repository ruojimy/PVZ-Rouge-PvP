"""Pin literal registry provider ownership and its remaining admission boundary."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_registry as reference
ROOT=reference.ROOT;sha=reference.sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('verification','negative','out'):ap.add_argument('--'+key,required=True)
    a=ap.parse_args();evidence={}
    for key,folder in [('regression',a.verification),('negative',a.negative)]:
        p=Path(folder).resolve()/'summary.json';r=json.loads(p.read_text(encoding='utf8'))
        if not r['passed']:raise ValueError('unpassed '+key)
        evidence[key]=dict(path=str(p),sha256=sha(p))
    for path,digest in json.loads((Path(a.verification)/'pinned.json').read_text(encoding='utf8')).items():
        if sha(Path(path))!=digest:raise ValueError('source drift '+path)
    entries=[]
    def add(path,cls,names,target):
        tree=ast.parse(path.read_text(encoding='utf8'),str(path));nodes=tree.body if cls is None else next(n.body for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
        for name in names:
            n=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
            entries.append(dict(source=str(path),source_sha256=sha(path),symbol=(cls+'.' if cls else '')+name,lines=[n.lineno,n.end_lineno],
                ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target=target,full_branch_coverage=False))
    add(reference.hero.BATTLE,'NativeBattle',('zombie_hero_proxies',),'collect_native_extras')
    add(reference.projectiles.SIMULATION,'Battle',('team_seats',),'seats_for / collect_native_extras')
    add(reference.TEAMS,None,('seats_for','scripted','team_mode'),'MatchMode / seats_for')
    tree=ast.parse(reference.hero.BATTLE.read_text(encoding='utf8'),str(reference.hero.BATTLE))
    matches=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Lambda)
        and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Index) and isinstance(t.slice.value,ast.Constant) and t.slice.value.value=='_pvp_target_extras' for t in n.targets)]
    if len(matches)!=1:raise ValueError('collector source ambiguity')
    n=matches[0];entries.append(dict(source=str(reference.hero.BATTLE),source_sha256=sha(reference.hero.BATTLE),symbol='NativeBattle.__init__._pvp_target_extras',lines=[n.lineno,n.end_lineno],
        ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target='TypedBattleState::omitted_targets / NativeObjectRegistry',full_branch_coverage=False))
    report=dict(schema=1,entries=entries,implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},evidence=evidence,
        ordered_key_replacement=True,shared_authoritative_bodies=True,actual_provider_composed_with_death=True,
        production_entry_switched=False,full_branch_coverage=False,full_product_acceptance=False,
        pending=['Full card admission and automatic registration/cleanup callers','Complete HeroProxy native template constructor and writable fields',
            'Remaining sourced hooks, bonus scheduler and full main tick','All remaining mechanisms, AI, network, spectators and replay',
            'Full old suite, source/branch closure, whole-battle parity, formal performance and final EXE/APK'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
