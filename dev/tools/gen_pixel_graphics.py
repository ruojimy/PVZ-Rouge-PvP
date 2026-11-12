"""Stage the original pixel-owning graphics classes separately from match recipe storage."""
import ast, hashlib, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import pvp2cpp as g
source=g.PVP/'native_animation.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
classes={'NativeGraphicsError','NativeImage','DeferredImage','_DeferredTransform','_Transforms','_Draw','_Pygame','DrawRecorder','NamespaceGraphics'}
kept=[]
for n in tree.body:
    if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign)):kept.append(n)
    elif isinstance(n,ast.ClassDef) and n.name in classes:kept.append(n)
    elif isinstance(n,ast.FunctionDef) and n.name in ('_plain','_template_atlas'):kept.append(n)
tree.body=kept
g.MODULES['native_animation_pixels']=g.ModuleInfo('native_animation_pixels',tree)
g.GEN_UI[0]=True
gen=g.Gen('native_animation_pixels');h,c=gen.run()
assert not gen.todo,gen.todo
c=c.replace('"sim/pvp/gen/pm_native_animation_pixels.h"','"ui/gen/pm_native_animation_pixels.h"')
pat=re.compile(r'\b(pm|init_deps)_(content_assets|expansion_assets|pvp64_sprite_atlas|pvp67_assets|pvp66_icons)\b')
c=pat.sub(lambda m:m[1]+'_ui_'+m[2],c)
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
stage=Path(args.out);stage.mkdir(parents=True,exist_ok=True)
h=h.replace('from modkit/pvp/native_animation_pixels.py','from modkit/pvp/native_animation.py (pixel classes)')
c=c.replace('from modkit/pvp/native_animation_pixels.py','from modkit/pvp/native_animation.py (pixel classes)')
for suffix,content in [('h',h),('cpp',c)]:
    target=stage/('pm_native_animation_pixels.'+suffix)
    if not target.exists() or target.read_text(encoding='utf-8')!=content:target.write_text(content,encoding='utf-8')
(stage/'provenance.json').write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'classes':sorted(classes),'functions':['_plain','_template_atlas'],'source_bodies':'unchanged AST; CPython extension install hooks omitted; production class methods preserved','todo':gen.todo},indent=2),encoding='utf-8')
print(len(h),len(c),'TODO',len(gen.todo))
