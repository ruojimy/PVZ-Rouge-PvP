"""Translate original patch definitions without PvP protection rewrites; never execute its game startup."""
import argparse,ast,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import pvp2cpp as g
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    source=g.EXTRA_SOURCES['patch1501'];tree=ast.parse(source.read_text(encoding='utf-8'))
    nodes=[]
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef)):nodes.append(node)
        elif isinstance(node,ast.Assign):
            names={x.id for x in node.targets if isinstance(x,ast.Name)}
            if not names.intersection(('__pvz_sb_plant_zombie_test_enabled','__pvz_sb_LOG_PATH')):nodes.append(node)
    tree.body=nodes
    g.fold_key_constants(tree)
    module='original_patch1501';g.DYNAMIC.add(module);g.MODULES[module]=g.ModuleInfo(module,tree)
    gen=g.DynGen(module);header,cpp=gen.run();assert not gen.todo,gen.todo
    (out/'pm_original_patch1501.h').write_text(header,encoding='utf-8');(out/'pm_original_patch1501.cpp').write_text(cpp,encoding='utf-8')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    (out/'original_patch_fingerprint.h').write_text('#pragma once\nnamespace pvz { inline constexpr const char* original_patch_source_sha256="'+digest+'"; }\n',encoding='utf-8')
    provenance=dict(source=str(source),sha256=digest,functions=len([n for n in nodes if isinstance(n,ast.FunctionDef)]),translation_todo=gen.todo,
        role='original isolated patch definitions; same startup/log exclusions as native_runtime.load_patch; no protect_patch_damage or high-solver rewriting',
        key_constants='immutable original string aliases folded to literal member keys',cpp_sha256=hashlib.sha256(cpp.encode()).hexdigest())
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8');print(json.dumps(provenance))
if __name__=='__main__':main()
