"""Pin chili body ownership, independent differential evidence and remaining wiring."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_chili as reference
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
    source=reference.patch.PATCH;env=reference.reference();tree=ast.parse(source.read_text(encoding='utf8'),str(source));entries=[]
    for name in env['raw_chili']:
        full=reference.P+name;matches=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==full]
        if len(matches)!=1:raise ValueError('ambiguous source '+full)
        n=matches[0];entries.append(dict(source=str(source),source_sha256=sha(source),symbol=full,lines=[n.lineno,n.end_lineno],
            ast_sha256=hashlib.sha256(ast.dump(n).encode()).hexdigest(),typed_target='ChiliEffects / ChiliDispatch / RecordId / TerrainEffects',
            scope='Literal original bodies with mandatory installed damage/spawn/plant services. Preserves captured list identity, live numeric ash indices, key presence, callback order, RNG and simulation clock. Full sourced wrapper composition is pending.',
            branch_syntax_nodes=sum(isinstance(x,(ast.If,ast.IfExp,ast.BoolOp,ast.Try)) for x in ast.walk(n)),full_branch_coverage=False))
    owned=[ROOT/'src/sim/pvp/gen/pm_native_patch.cpp',ROOT/'src/sim/pvp/gen/pm_patch1501.cpp',ROOT/'src/sim/pvp/shim/pm_cppcore.cpp',ROOT/'tools/pvp2cpp.py']
    report=dict(schema=1,entries=entries,source_ownership_review={str(p):sha(p) for p in owned},implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*') if p.is_file()},
        evidence=evidence,full_branch_coverage=False,whole_battle_supported=False,production_entry_switched=False,full_product_acceptance=False,
        pending=['Complete remaining sourced hooks and production lifecycle services; spawn retagging and owner launch have separate death-chain evidence','Connect simulation clock through the authoritative battle scheduler',
            'Complete HeroProxy template constructor and production extra-target collector',
            'Complete main battle tick, remaining mechanics, AI, multiplayer and replay','Old full suite, source/branch closure, whole-battle differential, formal performance and EXE/APK'])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(source_methods=len(entries),full_product_acceptance=False)))


if __name__=='__main__':main()
