"""Literal installed zombie-pea chain, protection, shotgun and hero launch."""
import argparse
import ast
import copy
import functools
import json
import math
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_squash as squash
import verify_fume as fume
import evidence_store
import evidence_archive
services=squash.services;death=squash.death;hero=squash.hero;plants=squash.plants;projectiles=squash.projectiles;chili=squash.chili;doom=squash.doom;patch=squash.patch
ROOT=hero.ROOT;P=squash.P;sha=squash.sha;difference=squash.difference;PVP70=squash.PVP70;PVP66=squash.PVP66

def reference():
    env=squash.reference();env['protected_damage_code']=fume.reference()['protected_damage_code']
    package='_typed72_oracle_pvp';module=types.ModuleType(package+'.simulation');projectiles.functions(projectiles.SIMULATION,['wrap_delta'],module.__dict__);sys.modules[module.__name__]=module
    pe=dict(math=math,__package__=package)
    for key in ('PEA_RANGE','SHOTGUN_FAN','VOLLEY_TICKS'):pe[key]=hero.constant(hero.ZSECRETS,key)
    env['pea_secrets_class']=hero.selected_class(hero.ZSECRETS,('_hero_pea','install_late','shotgun_volley','has','_own'),'PeaSecrets',pe)
    return env

class PeaExtension(squash.SquashExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        for u,v in zip(self.units,case['peas']['units']):u.update(copy.deepcopy(v))
        rebuilt={};exec(ref['protected_damage_code'],rebuilt)
        for name,replacement in rebuilt.items():
            if not name.startswith(P):continue
            original=self.ns[name]
            while hasattr(original,'__wrapped__'):original=original.__wrapped__
            original.__code__=replacement.__code__
        self.ns['_pvp_damage_amount']=self.g['_pvp_damage_amount']
        self.ns[P+'zombie_peas']=[];self.ns[P+'plant_zombie_shot_count']=0
        self.pea_raw={n:self.ns[P+n] for n in ('spawn_zombie_pea','update_one_zombie_pea','zombie_pea_hit')}
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env);env['bind']('spawn_zombie_pea',5,'source_zombie','zombies')
        for name in ('update_one_zombie_pea','zombie_pea_hit'):env['bind'](name,1,'pea','entities')
        self.pea_sourced=self.ns[P+'spawn_zombie_pea']
        self.b.patch=types.SimpleNamespace(ns=self.ns);self.b.tile=self.g['比'];self.b.width=self.g['总宽'];self.b.team_seats=lambda team:('plant','plant2')
        self.pea_secrets=ref['pea_secrets_class']();self.pea_secrets.b=self.b;self.pea_secrets.g=self.g;self.pea_secrets.enabled=False;self.pea_secrets.team={'散弹攻击'}
        self.pea_secrets.install_late();self.pea_secrets.team=set()
        self.g['_pvp_native_targets']=self.c
        old_knock=self.g['击退僵尸'];old_assets=self.ns[P+'patch_plant_zombie_assets']
        def assets(g):
            self.calls.append(['pea_assets']);self.before('pea_assets');r=old_assets(g);self.after('pea_assets');return r
        self.ns[P+'patch_plant_zombie_assets']=assets
        def surface(index,direction,amount):
            self.calls.append(['pea_surface',index,direction,amount]);self.before('pea_surface');r=self.c._surface_damage(index,direction,amount);self.after('pea_surface');return r
        def damage(index,direction,amount):
            self.calls.append(['pea_damage',index,direction,amount]);self.before('pea_damage');r=self.c._zombie_damage(index,direction,amount);self.after('pea_damage');return r
        def knock(index,force):
            self.calls.append(['pea_knockback',index,force]);self.before('pea_knockback');r=old_knock(index,force);self.after('pea_knockback');return r
        def player(amount):
            self.calls.append(['pea_player',amount]);self.before('pea_player');r=self.damage_player(amount);self.after('pea_player');return r
        self.pea_surface=surface;self.g.update(表面伤害僵尸=surface,伤害僵尸=damage,击退僵尸=knock,掉血=player)

    def operation(self,op):
        action=op['op'];ns=self.ns;g=self.g
        if action=='pea_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='pea_write':self.entity_fields(self.births[op['entity']],op['values'])
        elif action=='pea_environment':
            if 'pvp' in op:g['_pvp_native_targets']=self.c if op['pvp'] else None
            if 'enabled' in op:self.pea_secrets.enabled=op['enabled']
            if 'shotgun' in op:self.pea_secrets.team={'散弹攻击'} if op['shotgun'] else set()
            if 'surface' in op:g['表面伤害僵尸']=self.pea_surface if op['surface'] else None
            if 'tick' in op:self.b.engine.native_tick=op['tick'];g['_pvp_native_tick']=op['tick']
            for a,b in (('width','总宽'),('height','总高')):
                if a in op:g[b]=op[a]
        elif action=='pea_legacy':ns[P+'zombie_peas']=[self.births[i] for i in op['entities']]
        elif action=='pea_segment':return ns[P+'segment_hits_ellipse'](*(op['start']+op['end']+op['center']+op['radii']))
        elif action in ('pea_spawn','pea_volley'):
            t=self.target(op['source']) if op.get('source') is not None else None
            try:
                if action=='pea_volley':return self.pea_secrets.shotgun_volley(t) if t is not None else None
                mode=op.get('mode','pvp');fn=self.pea_raw['spawn_zombie_pea'] if mode=='raw' else self.pea_sourced if mode=='sourced' else ns[P+'spawn_zombie_pea']
                return fn(g,*op['point'],op['angle'],op.get('friendly',False),t)
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        elif action=='pea_player':return ns[P+'damage_player_from_zombie_pea'](g,op.get('direction',1.))
        elif action=='pea_all':return ns[P+'update_zombie_peas'](g)
        elif action=='pea_hero':
            self.b.width=op.get('width',960.);self.b.team_seats=lambda team:op['enemies']
            try:return self.pea_secrets._hero_pea(op['seat'])
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        elif action.startswith('pea_'):
            e=self.births[op['entity']]
            try:
                if action=='pea_is':return bool(ns[P+'is_zombie_pea'](e))
                if action=='pea_xy':return list(ns[P+'zombie_pea_xy'](e))
                if action=='pea_multiplier':return ns[P+'zombie_pea_fire_mult'](g,e)
                if action=='pea_torch':return ns[P+'zombie_pea_torch_check'](g,e)
                if action=='pea_damage_charmed':return ns[P+'damage_charmed_zombie_from_zombie_pea'](g,op['index'],self.target(op['target']),e,op.get('direction',1.))
                if action=='pea_hit':return (ns[P+'zombie_pea_hit'] if op.get('sourced',True) else self.pea_raw['zombie_pea_hit'])(g,e)
                if action=='pea_tick':return (ns[P+'update_one_zombie_pea'] if op.get('sourced',True) else self.pea_raw['update_one_zombie_pea'])(g,e,op.get('scale',48.),op.get('width',960.),op.get('height',576.))
                if action=='pea_splash':return ns[P+'zombie_pea_fire_splash'](g,e,*op['point'],direct_plant=self.all_plants[op['plant']] if op.get('plant') is not None else None,
                    direct_zombie=self.target(op['direct_zombie']) if op.get('direct_zombie') is not None else None,direct_player=op.get('direct_player',False))
                raise ValueError(action)
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row);row['pea_shots']=self.ns[P+'plant_zombie_shot_count'];row['pea_units']=[{k:u[k] for k in ('_pvp_card','_pvp_zs_volley') if k in u} for u in self.units]
        row['legacy_peas']=[self.fire_state(e) for e in self.ns[P+'zombie_peas']]
        for e in row['legacy_peas']:
            if P+'source_zombie_id' in e:e[P+'source_zombie_id']=self.identity(e[P+'source_zombie_id'])

def base():
    c=squash.base();c['peas']=dict(units=[{},{},{},{}]);c['services']['units'][0]['植物僵尸名']='豌豆僵尸';return c

def entity(pos=(240.,400.,0.,0.),name='僵尸豌豆',facing=1.):return dict(op='service_entity',name=name,position=list(pos),facing=facing)
def write(i,**values):return dict(op='pea_write',entity=i,values=values)
def spawn(**extra):return dict(op='pea_spawn',point=[240.,400.],angle=0.,**extra)

def make_cases():
    cases=[];rng=random.Random(72781)
    for i in range(96):
        c=base();c['operations']=[dict(op='pea_segment',start=[rng.uniform(-200,200),rng.uniform(-200,200)],end=[rng.uniform(-200,200),rng.uniform(-200,200)],center=[rng.uniform(-200,200),rng.uniform(-200,200)],radii=[rng.uniform(-20,100),rng.uniform(-20,100)]) for unused in range(4)]
        c['operations'] += [dict(op='pea_segment',start=[-2.,y],end=[2.,y],center=[0.,0.],radii=[0.,1.]) for y in (1.-1e-10,1.,1.+1e-10)]
        cases.append(('pea-segment-'+str(i),c))
    for i in range(96):
        c=base();c['seed']=76200+i;c['units'][0]['source']['_pvp_owner']=(None,'invalid','plant','zombie','plant2','zombie2')[i%6]
        c['operations']=[dict(op='lifecycle_hook',name='pea_assets',body=[dict(op='source_observe')]),dict(op='pea_spawn',point=[240.,400.],angle=(0.,90.,180.,270.,-30.,390.)[i%6],friendly=i%2==0,source=(None,0,'zombie','plant')[i//6%4],mode=('raw','sourced','pvp')[i//24%3],catch=True)]
        cases.append(('pea-spawn-'+str(i),c))
    for i in range(64):
        c=base();body=[dict(op='source_observe')]
        if i%4==0:body+=[dict(op='squash_roster',entities=[0])]
        if i%4==1:body+=[entity((600.,400.,0.,0.),'卷心菜')]
        if i%4==2:body+=[dict(op='pea_unit',unit=0,values={'_pvp_owner':'plant'})]
        c['operations']=[entity(),dict(op='lifecycle_hook',name='add',body=body,fail_before=i%8==0,fail_after=i%8==1),spawn(source=0,friendly=i%2==0,catch=True)]
        cases.append(('pea-spawn-callback-'+str(i),c))
    for i in range(64):
        c=base();c['peas']['units'][0].update(_pvp_card=('zombie:机枪僵尸','zombie:豌豆僵尸')[i%2],_pvp_zs_volley=(None,0.,100.,300.)[i//2%4]);c['units'][0]['source']['_pvp_owner']=('zombie','plant','zombie2','plant2')[i//8%4]
        c['operations']=[dict(op='pea_environment',enabled=i%3!=0,shotgun=True,tick=199),spawn(source=0,friendly=i%5==0,catch=True),dict(op='pea_environment',tick=200),spawn(source=0,catch=True),dict(op='pea_environment',tick=400),spawn(source=0,catch=True)]
        cases.append(('pea-shotgun-'+str(i),c))
    for i in range(80):
        c=base();c['globals']['秘籍']=['蓝火'] if i%2 else [];c['operations']=[dict(op='plant_original',cell=[8,5],name='火炬树桩'),entity((264.+(-36.,0.,36.,36.00001)[i%4],405.6+(0.,81.6,81.60001,-81.6)[i//4%4],0.,0.)),
            write(0,prev_x=264.+(-200.,0.,100.)[i//16%3],**{P+'zombie_pea_fire':(None,'','unknown','fire','blue')[i//16]}),dict(op='pea_environment',pvp=i%3!=0),dict(op='pea_torch',entity=0),dict(op='pea_multiplier',entity=0),dict(op='pea_hit',entity=0,sourced=False)]
        cases.append(('pea-torch-'+str(i),c))
    for i in range(96):
        c=base();c['globals']['模式']='正常模式' if i%2 else '我是僵尸';c['operations']=[dict(op='plant_original',cell=[8,5],name=('向日葵','地刺','地刺王','火炬树桩')[i%4]),
            dict(op='plant_write',plant=0,values={'植物血':(.5,5.,20.)[i//4%3],'_pvp_owner':'plant','_pvp_card':'producer'}),entity((340.,405.6,0.,0.)),write(0,prev_x=200.,prev_y=405.6,**{P+'zombie_pea_fire':('',None,'fire','blue')[i//12%4]}),
            dict(op='lifecycle_hook',name='clear',fail_before=i%3==0,fail_after=i%3==1),dict(op='pea_hit',entity=0,sourced=i%3!=0)]
        c['damage'].update(until=2500,factor=(0.,.25,1.,2.)[i//24],cards={'producer':True});cases.append(('pea-plant-hit-'+str(i),c))
    for i in range(96):
        c=base();c['services']['units'][1]['魅惑']=None;c['units'][1]['body']['血量']=1000.
        if i%4==0:c['services']['units'][1].update(手持='钢门',手持血量=100.)
        if i%4==1:c['services']['units'][1].update(防具='铁桶',防具血量=100.)
        c['operations']=[entity(),write(0,**{P+'zombie_pea_fire':('','fire','blue')[i%3]}),dict(op='pea_environment',surface=i%2==0),
            dict(op='lifecycle_hook',name='pea_surface',fail_before=i%4==0,fail_after=i%4==1),dict(op='lifecycle_hook',name='pea_damage',fail_before=i%5==0,fail_after=i%5==1),
            dict(op='pea_damage_charmed',entity=0,index=(1,99)[i//48],target=1,direction=(-1.,0.,1.)[i//16%3])]
        if i>=48:c['operations'].insert(2,write(0,追踪=None if i%2 else 0.))
        cases.append(('pea-charmed-damage-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][1]['魅惑']=None;c['globals']['模式']='正常模式' if i%2 else '我是僵尸';c['services']['units'][2]['魅惑']=0.
        if i%4==0:c['services']['units'][1]['死']=False
        if i%4==1:c['services']['units'][1]['灰烬']=None
        c['operations']=[entity((380.,380.,0.,0.)),write(0,prev_x=220.,prev_y=380.,**{P+'source_zombie_id':{'unit':1} if i%3==0 else None,P+'zombie_pea_fire':('','blue')[i%2]}),dict(op='pea_hit',entity=0,sourced=i%3!=0)]
        cases.append(('pea-charmed-hit-'+str(i),c))
    for i in range(64):
        c=base();c['globals']['模式']='正常模式' if i%2 else '我是僵尸';c['globals']['玩家位置']=[240.,432.,5.,7.]
        c['operations']=[dict(op='lifecycle_hook',name='pea_player',fail_before=i%4==0,fail_after=i%4==1),dict(op='pea_player',direction=(-1.,0.,1.)[i//16%3]),entity((240.,384.,0.,0.)),dict(op='pea_hit',entity=0,sourced=i%3!=0)]
        cases.append(('pea-player-'+str(i),c))
    for i in range(64):
        c=base();c['globals']['模式']='正常模式';c['services']['units'][1]['魅惑']=None;c['services']['units'][2]['魅惑']=0.
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_original',cell=[8,6],name='向日葵'),dict(op='plant_original',cell=[8,7],name='火炬树桩'),entity(),write(0,**{P+'zombie_pea_fire':(None,'fire','blue','unknown')[i%4]}),
            dict(op='pea_environment',pvp=i%5!=0),dict(op='pea_splash',entity=0,point=[(240.,280.,320.,360.)[i//4%4],400.],plant=0 if i%2 else None,direct_zombie=1 if i%3==0 else None,direct_player=i%4==0)]
        cases.append(('pea-splash-'+str(i),c))
    for i in range(80):
        c=base();c['operations']=[entity(((-96.,1056.,100.)[i%3],(-96.,672.,100.)[i//3%3],5.,7.)),write(0,x=None,y=None,vx=(None,0.,1.,-1.)[i%4],vy=(None,0.,1.,-1.)[i//4%4],age=(None,3999.,4000.,-2.)[i//16%4],**{P+'native_move':(None,False,True)[i%3]}),dict(op='pea_tick',entity=0,sourced=i%2==0),dict(op='pea_all')]
        cases.append(('pea-movement-age-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['模式']='正常模式';body=[dict(op='source_observe')]
        # The surviving native pea is entity 1. Install a visibly different
        # list so writing the old filter result into the new roster is observable.
        if i%3==0:body += [dict(op='squash_roster',entities=[] if i%2 else [1,1])]
        if i%3==1:body += [entity((500.,100.,0.,0.),'卷心菜')]
        if i%3==2:body += [dict(op='pea_legacy',entities=[1])]
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_write',plant=0,values={'植物血':1.}),entity((264.,405.6,0.,0.)),entity((500.,100.,0.,0.)),dict(op='pea_legacy',entities=[0,1]),
            dict(op='lifecycle_hook',name='clear',body=body,fail_after=i>=24),dict(op='pea_all'),dict(op='pea_all')]
        cases.append(('pea-list-identity-'+str(i),c))
    for i in range(96):
        c=base();seat=('zombie','zombie2')[i%2];x=(240.,940.,20.,500.)[i//2%4]
        c['heroes'][seat]['玩家位置']=[x,432.,0.,0.];c['heroes'][seat]['玩家方向']=(-1.,0.,1.)[i//8%3]
        c['heroes']['plant']['玩家位置']=[(300.,10.,900.,500.)[i//24],400.,0.,0.];c['heroes']['plant2']['玩家位置']=[400.,432.,0.,0.]
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_write',plant=0,values={'_pvp_owner':'plant'}),dict(op='pea_hero',seat=seat,enemies=['plant','plant2'],width=960.,catch=True),dict(op='pea_all')]
        cases.append(('pea-hero-'+str(i),c))
    for i in range(48):
        c=base();c['services']['units'][1]['魅惑']=None;c['units'][1]['body']['血量']=1000.
        hook=('pea_surface','pea_damage','pea_knockback')[i%3]
        body=[dict(op='roster_replace',targets=([3,2,0],[3,2,1,0],[1])[i//3%3]),dict(op='source_observe')]
        c['operations']=[entity(),dict(op='lifecycle_hook',name=hook,body=body,fail_before=i%4==0,fail_after=i%4==1),
            dict(op='pea_damage_charmed',entity=0,index=1,target=1),dict(op='pea_damage_charmed',entity=0,index=0,target=1)]
        cases.append(('pea-nested-index-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['模式']='我是僵尸' if i%2 else '正常模式';c['services']['units'][1]['魅惑']=None
        body=[dict(op='roster_replace',targets=[3]),dict(op='plant_roster_replace',plants=[]),dict(op='write',target='globals',values={'模式':'正常模式'})]
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_original',cell=[8,6],name='向日葵'),dict(op='plant_write',plant=0,values={'植物血':1.}),entity((280.,405.6,0.,0.)),write(0,prev_x=200.,prev_y=405.6,**{P+'zombie_pea_fire':'blue'}),
            dict(op='lifecycle_hook',name='clear',body=body,fail_after=i%3==0),dict(op='pea_hit',entity=0,sourced=i%3!=0)]
        cases.append(('pea-legacy-retained-view-'+str(i),c))
    for i,owner in enumerate((None,'invalid','plant','zombie','plant2','zombie2')):
        for j in range(8):
            c=base();c['heroes']['plant']['玩家位置']=[240.,432.,3.,5.];c['heroes']['zombie']['玩家位置']=[480.,432.,7.,9.]
            c['operations']=[entity((240.,384.,0.,0.)),write(0,_pvp_owner=owner),dict(op='lifecycle_hook',name='pea_player',body=[dict(op='source_observe')]),
                dict(op='pea_tick' if j<4 else 'pea_hit',entity=0,sourced=j%2==0,catch=True)]
            if j%4>=2:c['operations']=[dict(op='chili_scope',unit_source=0,target='zombie',owner='plant',phase='entities',body=c['operations'])]
            cases.append(('pea-source-context-'+str(i)+'-'+str(j),c))
    for i in range(36):
        c=base();x,y=264.,405.6;delta=(-1e-8,0.,1e-8)[i%3];boundary=i//3%4
        impact=([x+62.4+delta,y],[x-62.4+delta,y],[x,y+129.6+delta],[x,y-48.+delta])[boundary]
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),entity(),write(0,**{P+'zombie_pea_fire':('fire','blue','unknown')[i//12]}),dict(op='pea_splash',entity=0,point=impact,direct_player=True)]
        cases.append(('pea-splash-boundary-'+str(i),c))
    for i in range(48):
        c=base();c['heroes']['plant']['玩家位置']=[300.,400.,0.,0.]
        body=[dict(op='source_observe')]
        if i%3==0:body+=[dict(op='squash_roster',entities=[0])]
        if i%3==1:body+=[entity((600.,200.,0.,0.),'卷心菜')]
        c['operations']=[entity(),dict(op='lifecycle_hook',name=('add','pea_assets')[i%2],body=body,fail_before=i%4==0,fail_after=i%4==1),dict(op='pea_hero',seat='zombie',enemies=['plant','plant2'],catch=True)]
        cases.append(('pea-hero-callback-'+str(i),c))
    for i in range(24):
        c=base();c['operations']=[entity(name=('豌豆','僵尸豌豆','卷心菜')[i%3]),write(0,**{'僵尸豌豆弹':(None,False,True)[i//3%3]}),dict(op='pea_is',entity=0),dict(op='pea_xy',entity=0),dict(op='pea_all')]
        cases.append(('pea-identification-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[PVP66,PVP70,exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('pea_probe.cpp','verify_squash.py','verify_fume.py','squash_probe.cpp','service_probe.cpp','verify_services.py','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=plants.protection.reference();chili_ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:PeaExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-zombie-pea-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks','whole native driver','complete custom content scheduler','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
