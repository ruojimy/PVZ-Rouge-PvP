"""Merge only owned 72 input changes onto existing reviewed generated C++.

The old translator output is a merge base, not a reason to regenerate every
module or discard live hand repairs. All conflict files remain reviewable.
"""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
work=root/'build/pvp72-generation'
git=Path(r'C:\Program Files\Git\cmd\git.exe')
sim='balance catalog native_content native_targets native_battle zombie_secrets pvp70_content pvp58_vines native_placement zombie_secret_catalog pvp58_catalog pvp71_catalog pve coop_progress'.split()
ui='app draft_advisor ui_data hud battle_view replay performance_probe room pve_ui'.split()
dual=re.compile(r'\b(pm|init_deps)_(content_assets|expansion_assets|pvp64_sprite_atlas|pvp67_assets|pvp66_icons)\b')
records=[]
for kind,names in [('sim',sim),('ui',ui)]:
    for stage in ('base','changed'):
        folder=work/stage/kind/'gen'
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        if stage=='base':env['PVZ72_TRANSLATION_BASELINE']='1'
        else:env.pop('PVZ72_TRANSLATION_BASELINE',None)
        run=subprocess.run([sys.executable,str(root/'tools/pvp2cpp.py'),str(folder)]+names,cwd=str(root),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (work/(stage+'-'+kind+'.log')).write_bytes(run.stdout)
        if run.returncode or b'total TODO 0' not in run.stdout:raise RuntimeError('Generation failed: '+str(folder))
        if kind=='ui':
            for p in folder.glob('pm_*'):
                t=p.read_text(encoding='utf8');p.write_text(dual.sub(lambda m:m[1]+'_ui_'+m[2],t),encoding='utf8')
    for name in names:
        for ext in ('h','cpp'):
            base=work/'base'/kind/'gen'/('pm_'+name+'.'+ext)
            changed=work/'changed'/kind/'gen'/base.name
            live=root/('src/sim/pvp/gen' if kind=='sim' else 'src/ui/gen')/base.name
            if changed.read_bytes()==base.read_bytes():continue
            result=subprocess.run([str(git),'merge-file','-p',str(live),str(base),str(changed)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            out=work/(kind+'-'+live.name+'.merged')
            out.write_bytes(result.stdout)
            if result.returncode:
                records.append({'file':str(live.relative_to(root)),'conflict':str(out),'code':result.returncode})
            else:
                if live.read_bytes()!=result.stdout:live.write_bytes(result.stdout)
                records.append({'file':str(live.relative_to(root)),'sha256':hashlib.sha256(result.stdout).hexdigest()})
(work/'merge-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
conflicts=[r for r in records if 'conflict' in r]
print('Merged',len(records)-len(conflicts),'files; conflicts:',len(conflicts))
for item in conflicts:print(item['conflict'])
raise SystemExit(bool(conflicts))
