"""Literal doom effect functions plus current PvP target wrapper on one world.

This verifies actual effect bodies. Sourced death dispatch and the complete
combat driver remain separate required integrations.
"""
import argparse
import ast
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_plants as plants
import verify_projectiles as projectiles
from verify_stages import sha,difference
import evidence_store
import evidence_archive
hero=plants.hero;patch=plants.patch;ROOT=hero.ROOT
LEGACY=hero.REF/'modkit/pvp/legacy_fixes.py'
NATIVE_PATCH=hero.REF/'modkit/pvp/native_patch.py'
P=patch.PREFIX


def reference():
    env=plants.load_terrain_reference()
    names=('doom_zombie_world_point','chili_zombie_world_point','spawn_doom_zombie_visuals','doom_zombie_knock_player',
        'doom_zombie_destroy_blocks','spawn_doom_zombie_explosion','spawn_effect_entity','append_unique_sequence',
        'plant_world_point','squash_zombie_kill_plant','zombie_target_point','is_charmed_zombie','plant_zombie_head_center')
    projectiles.functions(patch.PATCH,[P+n for n in names],env);env[P+'PLANT_ZOMBIE_CONFIG']={}
    legacy={'_PREFIX':P};projectiles.functions(LEGACY,['_doom_targets'],legacy);env['pvp_doom_targets']=legacy['_doom_targets']
    nodes=[n for n in ast.walk(ast.parse(NATIVE_PATCH.read_text(encoding='utf8'),str(NATIVE_PATCH))) if isinstance(n,ast.FunctionDef) and n.name=='pvp_doom']
    if len(nodes)!=1:raise ValueError('doom wrapper source ambiguity')
    env['pvp_doom_code']=compile(ast.Module(body=nodes,type_ignores=[]),str(NATIVE_PATCH),'exec');return env


class DoomExtension(plants.PlantExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);cfg=case['doom_world'];self.births=[]
        self.g['其它图']=list(cfg.get('images',[]));self.env[P+'doom_zombie_explode_count']=0
        self.extras=None if cfg.get('extras',[]) is None else [self.target(t) for t in cfg.get('extras',[])]
        self.g['_pvp_target_extras']=self.extra_targets if self.extras is not None else None
        wrapper=dict(targets=self.c,self=plants.types.SimpleNamespace(ns=ref),_doom_targets=ref['pvp_doom_targets'])
        exec(ref['pvp_doom_code'],wrapper);self.env[P+'doom_zombie_ash_targets']=wrapper['pvp_doom']
        self.raw_add=self.g['新增实体'];self.g['__pvz_sb_add_entity_original']=self.add_entity
        self.g['摧毁方块']=self.destroy_block
        raw_ash=self.c.originals['灰烬僵尸']
        def ash(*args):
            result=raw_ash(*args);self.after('ash');return result
        self.c.originals['灰烬僵尸']=ash

    def extra_targets(self):
        self.calls.append(['extras']);self.before('extras');self.after('extras');return self.extras

    def add_entity(self,name,facing,pos):
        self.calls.append(['add',name,facing,copy.deepcopy(pos)]);self.before('add');self.raw_add(name,facing,pos)
        self.births.append(self.g['实体'][-1]);self.after('add')

    def destroy_block(self,y,x):
        self.calls.append(['destroy',y,x]);self.before('destroy');self.destroy_pvp(y,x);self.after('destroy')

    def operation(self,op):
        action=op['op'];result=None
        if action in ('doom','doom_targets'):
            self.throw_raw=op.get('throw_raw',False)
            try:
                if action=='doom':result=self.env[P+'spawn_doom_zombie_explosion'](self.g,self.units[op['unit']])
                else:result=self.env[P+'doom_zombie_ash_targets'](self.g,self.units[op['unit']],*op['point'],op.get('scale',self.g['比']))
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
            finally:self.throw_raw=False
        elif action in ('doom_visuals','doom_blocks','doom_knock'):
            name={'doom_visuals':'spawn_doom_zombie_visuals','doom_blocks':'doom_zombie_destroy_blocks','doom_knock':'doom_zombie_knock_player'}[action]
            result=self.env[P+name](self.g,*op['point'],op.get('scale',self.g['比']))
        elif action=='kill_plant':result=self.env[P+'squash_zombie_kill_plant'](self.g,self.all_plants[op['plant']])
        elif action=='effect_roster_replace':self.g['实体']=[self.births[i] for i in op['births']]
        elif action=='doom_write_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='doom_write_proxy':dict.update(self.ctx.get_proxy(op['target']),copy.deepcopy(op['values']))
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row);row['doom_state']=dict(images=self.g['其它图'],explosions=self.env[P+'doom_zombie_explode_count'])
        row['doom_state'].update({k:self.g[k] for k in ('核爆','抖屏') if k in self.g})
        row['effect_births']=copy.deepcopy(self.births)
        for e in row['effect_births']:
            if '_pvp_instant_attack' in e:e['_pvp_instant_attack_text']=str(e.pop('_pvp_instant_attack'))
        row['doom_unit_fields']=[{k:u[k] for k in ('大小','死','植物僵尸','植物僵尸名') if k in u} for u in self.units]
        row['doom_proxy_fields']={s:{k:u[k] for k in ('大小','死') if k in u} for s,u in self.c.proxies.items()}


def base():
    c=plants.base(12,13);c['units']=[projectiles.unit(240.,288.,owner='zombie')];c['doom_world']=dict(extras=[],images=[]);return c


def make_cases():
    cases=[]
    for i in range(64):
        c=base();c['seed']=7100+i;charmed=i%2==0
        if charmed:c['units'][0]['source']['魅惑']=None if i%4==0 else 0.
        for n in range(8):
            u=projectiles.unit(240.+(n-3)*80.,288.+(n%3-1)*140.,owner='plant' if n%2 else 'zombie');u['body']['血量']=600. if n%3==0 else 50.
            if n%2:u['source']['魅惑']=0.
            if n==6:u['body']['灰烬']=None
            c['units'].append(u)
        c['doom_world']['extras']=['plant','zombie','plant2','zombie2'];c['doom_world']['images']=['毁灭2','保留图']
        body=[]
        for n in range(6):body += [dict(op='plant_original',cell=[3+n%3,2+n],name='南瓜头' if n==2 else '向日葵')]
        body += [dict(op='plant_original',cell=[5,4],name='豌豆射手'),dict(op='doom_write_unit',unit=4,values={'死':None if i%3==0 else False}),
            dict(op='doom_write_unit',unit=2,values={'大小':(.1,.35,1.,2.)[i%4],'植物僵尸':i%7==0,'植物僵尸名':'豌豆射手僵尸'}),
            dict(op='tile_replace',cell=[5,4],value={'方块':'基岩' if i%3==0 else '石','植物':True}),dict(op='doom',unit=0)]
        if i%5==0:body.insert(-1,dict(op='lifecycle_hook',name='clear',fail_after=True))
        if i%7==0:body.insert(-1,dict(op='lifecycle_hook',name='add',fail_after=True))
        if i%11==0:body.insert(-1,dict(op='lifecycle_hook',name='destroy',fail_before=True))
        c['operations']=[hero.context(body,owner='plant' if charmed else 'zombie',target='zombie' if charmed else 'plant',phase='zombies',unit_source=0)]
        cases.append(('doom-composed-'+str(i),c))
    for i in range(36):
        c=base();c['units'][0]['source']['魅惑']=0.;c['units'] += [projectiles.unit(x,y,owner='zombie') for x,y in ((480.,288.),(480.0000001,288.),(240.,559.2),(240.,559.2000001),(0.,288.),(-.0000001,288.))]
        c['doom_world']['extras']=['zombie'];body=[dict(op='doom_write_unit',unit=1+i%6,values={'大小':(None,.1,.35,1.,2.,3.)[i//6]})]
        body.append(dict(op='doom_targets',unit=0,point=[240.,288.],scale=48.));c['operations']=[hero.context(body,unit_source=0)]
        cases.append(('doom-range-'+str(i),c))
    for i in range(16):
        c=base();c['units'][0]['source']['魅惑']=0.;c['units'] += [projectiles.unit(240.,288.,owner='zombie') for n in range(3)]
        c['doom_world']['extras']=['zombie','zombie'];replacement=[0,3] if i%4==1 else [0,2,3] if i%2==0 else [0,3,2,'zombie']
        body=[dict(op='lifecycle_hook',name='ash',body=[dict(op='roster_replace',targets=replacement)]),
            dict(op='doom_targets',unit=0,point=[240.,288.],throw_raw=i%4==0,catch=True)]
        if i%3==0:body.insert(0,dict(op='lifecycle_hook',name='extras',body=[dict(op='roster_replace',targets=[0,1,2,3])]))
        c['operations']=[hero.context(body,unit_source=0)];cases.append(('doom-live-roster-'+str(i),c))
    for i in range(16):
        c=base();body=[dict(op='lifecycle_hook',name='add',fail_before=i%4==0,fail_after=i%4==1,
            body=[dict(op='effect_roster_replace',births=[] if i%2 else [0])]),dict(op='doom_visuals',point=[240.,288.],scale=(1.,24.,48.,80.)[i//4])]
        c['operations']=[hero.context(body,owner='zombie',target='plant',unit_source=0)] if i%2 else body
        cases.append(('doom-visual-hook-'+str(i),c))
    for i in range(48):
        c=base();x=(-240.0000001,-240.,0.,240.,240.0000001,1.)[i%6];y=(-240.0000001,-240.,240.,240.0000001)[i//6%4]
        c['globals']['玩家位置']=[x,y,.3,-.5];c['operations']=[dict(op='doom_knock',point=[0.,0.],scale=48.)]
        if i>=24:c['globals'].pop('玩家位置')
        cases.append(('doom-knock-boundary-'+str(i),c))
    for i in range(16):
        c=base();c['operations']=[dict(op='plant_original',cell=[3,3],name='向日葵'),dict(op='plant_original',cell=[3,3],name='南瓜头'),
            dict(op='lifecycle_hook',name='clear',fail_before=i%4==0,fail_after=i%4==1,body=[dict(op='plant_roster_replace',plants=[0])]),
            dict(op='kill_plant',plant=i%2),dict(op='doom_blocks',point=[(i%4-1)*48.,(i//4-1)*48.],scale=48.)]
        cases.append(('doom-plant-clear-'+str(i),c))
    for i in range(4):
        c=base();c['units'] += [projectiles.unit(240.,288.,owner='zombie') for n in range(2)];c['units'][1]['source']['魅惑']=0.
        body=[dict(op='plant_original',cell=[5,5],name='魅惑菇'),dict(op='lifecycle_hook',name='clear',body=[dict(op='doom_write_unit',unit=0,values={'魅惑':None if i%2 else 0.})]),
            dict(op='doom_targets',unit=0,point=[240.,288.])]
        c['operations']=[hero.context(body,owner='zombie',target='plant',unit_source=0)];cases.append(('doom-source-capture-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),LEGACY,NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=plants.protection.reference();doom_ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:DoomExtension(ctx,c,pref,doom_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-doom-effects',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['sourced PvP death wrapper binding','full HeroProxy template constructor','chili effect body','full battle','network/replay','dynamic invalid record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
