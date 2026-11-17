"""Owned touch source generation and small Application boundary hooks."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
CHECK='--check' in sys.argv
MANIFEST=ROOT/'tools/pvp744_controls_sources.json'
files=['tools/pvp72_sources/touch.py','src/ui/gen/pm_touch.cpp','src/ui/gen/pm_touch.h']
if '--generate' in sys.argv:
    target=ROOT/'build/pvp744-controls-generation/ui/gen'
    p=subprocess.run([sys.executable,str(ROOT/'tools/pvp2cpp.py'),str(target),'touch'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if p.returncode or 'total TODO 0' not in p.stdout:raise RuntimeError(p.stdout+p.stderr)
    for ext in ('cpp','h'):
        (ROOT/f'src/ui/gen/pm_touch.{ext}').write_bytes((target/f'pm_touch.{ext}').read_bytes())
    MANIFEST.write_text(json.dumps({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n','utf-8')

path=ROOT/'src/ui/gen/pm_app.cpp'
old=path.read_text('utf-8');text=old
def insert(marker,anchor,addition):
    global text
    if marker in text:return
    if text.count(anchor)!=1:raise RuntimeError(f'Control hook anchor {marker}: {text.count(anchor)}')
    text=text.replace(anchor,anchor+addition,1)
insert('// PvP744 control options load',
       '            pvz::setitem(a_state, SV("touch_layout"), (L_layout_overrides).call(Args{py::m_get(L_value, SV("touch_layout"))}));\n',
       '            pvz::setitem(a_state,SV("touch_options"),pm_touch::f_control_options(Args{py::m_get(L_value,SV("touch_options"))})); // PvP744 control options load\n')
if '// PvP744 control options save' not in text:
    start=text.index('V C_Application::m_save_settings(')
    line=text.index('    L_value = ',start);end=text.index('\n',line)
    text=text[:end]+'\n    pvz::setitem(L_value,SV("touch_options"),pm_touch::f_control_options(Args{py::m_get(a_state,SV("touch_options"))})); // PvP744 control options save'+text[end:]
if '// PvP744 control options action' not in text:
    start=text.index('V C_Application::m_action(')
    anchor='    L_kind = rd(L_action, V(0.0));\n'
    end=text.index(anchor,start)+len(anchor)
    text=text[:end]+'    if(L_kind==SV("touch_option")&&L_action.len()==3){callm(a_touch,SY("editor_option"),Args{L_action.idx(1),L_action.idx(2)});return V::none();} // PvP744 control options action\n'+text[end:]
insert('// PvP744 control options reset',
       '        pvz::setitem(a_state, SV("touch_layout"), py_dict({}));\n',
       '        pvz::setitem(a_state,SV("touch_options"),V::dict()); // PvP744 control options reset\n')
if CHECK:
    if old!=text:raise SystemExit('Stale PvP744 controls boundary hooks')
    if not MANIFEST.exists() or json.loads(MANIFEST.read_text('utf-8'))!={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}:raise SystemExit('Stale touch source generation: run tools/pvp744_controls_hooks.py --generate')
else:
    if old!=text:path.write_text(text,'utf-8')
print('PvP744 controls hooks: '+('checked' if CHECK else 'applied'))
