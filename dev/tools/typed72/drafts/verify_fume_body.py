"""Installed fumeshroom chain, numeric protection and native visual timing."""
import argparse
import ast
import copy
import functools
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_services as services
death=services.death;hero=services.hero;plants=services.plants;projectiles=services.projectiles;chili=services.chili;doom=services.doom;patch=services.patch
ROOT=hero.ROOT;P=death.P;sha=death.sha;difference=death.difference;PVP70=services.PVP70
FIELDS=('眩晕',P+'fumeshroom_zombie_cd',P+'fumeshroom_zombie_attack_angle',P+'fumeshroom_zombie_damage_done',P+'fumeshroom_zombie_bubble_tick')


def reference():
    env=services.reference();compiler=dict(ast=ast,lru_cache=functools.lru_cache,NativeGateError=RuntimeError)
    projectiles.functions(plants.protection.PROTECTION,['_patch_damage_code'],compiler)
    env['protected_damage_code']=compiler['_patch_damage_code'](patch.PATCH.read_text(encoding='utf8'));return env


class FumeExtension(services.ServiceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        for u,v in zip(self.units,case['fume']['units']):u.update(copy.deepcopy(v))
        self.ns[P+'fumeshroom_bubbles']=[];self.ns[P+'fumeshroom_bubble_last_update']=0.;self.ns[P+'fumeshroom_zombie_attack_count']=0
        ctx.constructor_patch._clock=lambda:self.native_time
        rebuilt={};exec(ref['protected_damage_code'],rebuilt)
        for name,replacement in rebuilt.items():
            if not name.startswith(P):continue
            original=self.ns[name]
            while hasattr(original,'__wrapped__'):original=original.__wrapped__
            original.__code__=replacement.__code__
        self.ns['_pvp_damage_amount']=self.g['_pvp_damage_amount']
        self.raw_update=self.ns[P+'update_fumeshroom_zombie'];self.raw_line=self.ns[P+'apply_fumeshroom_line_attack']
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env)
        for n in ('update_fumeshroom_zombie','apply_fumeshroom_line_attack'):env['bind'](n,1,'zombie','zombies')
        original=self.g['伤害僵尸'];player=self.g['掉血']
        def damage(index,direction,amount):
            self.calls.append(['fume_damage',index,direction,amount]);self.before('fume_damage');original(index,direction,amount);self.after('fume_damage')
        def damage_player(amount):
            self.calls.append(['fume_player',amount]);self.before('fume_player');player(amount);self.after('fume_player')
        self.g['伤害僵尸']=damage;self.g['掉血']=damage_player

    def describe(self,t):
        if t is None:return None
        kind,index,obj,point,direction,angle=t
        label={'plant':next(i for i,p in enumerate(self.all_plants) if p is obj)} if kind=='plant' else self.label(obj) if kind=='zombie' else None
        return [kind,index,label,list(point),direction,angle]

    def operation(self,op):
        action=op['op'];ns=self.ns;g=self.g
        if action=='fume_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='fume_environment':
            if 'time' in op:self.native_time=op['time']
            for a,b in (('width','总宽'),('height','总高')):
                if a in op:g[b]=op[a]
        elif action=='fume_ray':return ns[P+'ray_hits_circle'](g,op['origin'],op['angle'],op['point'],op['radius'],op['length'])
        elif action=='fume_within':return ns[P+'point_within_tiles'](g,op['center'],op['point'],op['radius'])
        elif action=='fume_metal':return ns[P+'zombie_has_active_metal'](self.target(op['target']))
        elif action=='fume_stun':return ns[P+'apply_fumeshroom_thunder_stun'](g,self.target(op['target']),op['point'])
        elif action=='fume_thunder':return ns[P+'fumeshroom_zombie_is_thunder'](g,self.units[op['unit']])
        elif action=='fume_damage_plant':return ns[P+'damage_plant_from_fumeshroom'](g,self.all_plants[op['plant']],op['amount'])
        elif action=='fume_damage_player':return ns[P+'damage_player_from_fumeshroom'](g,op.get('direction',1.))
        elif action=='fume_damage_unit':return ns[P+'damage_zombie_from_fumeshroom'](g,op['index'],self.target(op['target']),op['amount'],op.get('direction',1.))
        elif action=='fume_bubbles':return ns[P+'spawn_fumeshroom_bubble_burst'](g,op['center'],op['angle'],self.config(op,'大喷菇僵尸'),op.get('blue',False))
        elif action=='fume_bubble_tick':return ns[P+'update_fumeshroom_bubbles'](g,op.get('time'))
        elif action in ('fume_shoot_tick','fume_pick','fume_animate','fume_update','fume_line'):
            u=self.units[op['unit']];c=self.config(op,'大喷菇僵尸')
            if action=='fume_shoot_tick':return [ns[P+'fumeshroom_zombie_shoot_tick'](u,c),ns[P+'fumeshroom_zombie_fire_frames'](c),ns[P+'fumeshroom_visual_tick'](c)]
            if action=='fume_pick':
                t,center=ns[P+'pick_fumeshroom_zombie_target'](g,u,c);return [self.describe(t),list(center)]
            if action=='fume_animate':return ns[P+'update_fumeshroom_zombie_fire_animation'](g,u,c)
            if action=='fume_update':return (ns[P+'update_fumeshroom_zombie'] if op.get('sourced',True) else self.raw_update)(g,u,c)
            return (ns[P+'apply_fumeshroom_line_attack'] if op.get('sourced',True) else self.raw_line)(g,u,op['center'],op['angle'],c)
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row);row['fume_units']=[{k:u[k] for k in FIELDS if k in u} for u in self.units]
        row['fume_bubbles']=copy.deepcopy(self.ns[P+'fumeshroom_bubbles']);row['fume_state']=dict(attacks=self.ns[P+'fumeshroom_zombie_attack_count'],last_update=self.ns[P+'fumeshroom_bubble_last_update'],time=self.native_time)


def base():
    c=services.base();c['services']['units'][0]['植物僵尸名']='大喷菇僵尸';c['fume']=dict(units=[{},{},{},{}]);return c


def write(i,**v):return dict(op='fume_unit',unit=i,values=v)


def make_cases():
    cases=[]
    for i in range(96):
        c=base();angle=(0.,90.,180.,270.,45.,-30.,359.,720.)[i%8];c['operations']=[]
        for offset in (-.000001,0.,.000001):
            c['operations'].append(dict(op='fume_ray',origin=[240.,400.],angle=angle,point=[(234.,240.,528.,534.)[i//8%4]+offset,400.+(-24.,0.,24.)[i//32]],radius=24.,length=6.))
        c['operations'].append(dict(op='fume_within',center=[240.,400.],point=[528.,784.],radius=(10.,-10.,9.,0.)[i%4]))
        cases.append(('fume-geometry-'+str(i),c))
    for i in range(96):
        c=base();c['units'][0]['body']['方向']=(-1.,0.,1.)[i%3]
        if i%2:c['services']['units'][0]['魅惑']=None
        for n in (1,2):c['units'][n]['body']['位置']=[(200.,280.,720.,1200.)[i//3%4],432.,0.,0.]
        c['services']['units'][1]['魅惑']=0.
        if i%6==0:c['services']['units'][1]['死']=False
        if i%6==1:c['services']['units'][1]['灰烬']=None
        if i%6==2:c['units'][1]['body']['血量']=0.
        c['globals']['模式']='正常模式' if i%4<2 else '我是僵尸';c['damage']['hero_targets']=['plant','zombie','plant2','zombie2']
        c['operations']=[dict(op='plant_original',cell=[8,4],name='向日葵'),dict(op='plant_original',cell=[8,7],name='坚果'),
            dict(op='fume_pick',unit=0,config={'range_tiles':(None,0.,1.,-9.,9.,30.)[i//16]}),dict(op='roster_replace',targets=[2,1,0,3]),dict(op='fume_pick',unit=0)]
        cases.append(('fume-target-'+str(i),c))
    for i in range(96):
        c=base();c['seed']=74500+i
        if i%2:c['services']['units'][0]['魅惑']=None
        c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        c['services']['units'][1].update(手持='钢门',手持血量=100.)
        c['services']['units'][2].update(防具='铁桶',防具血量=20.,魅惑=0.)
        if i%3==0:c['services']['units'][3]['死']=False
        for h in c['heroes'].values():h['秘籍']=['雷霆'] if i%3 else []
        c['globals']['秘籍']=['雷霆'] if i%4==1 else [];c['globals']['模式']='正常模式' if i%4<2 else '我是僵尸'
        c['damage']['hero_targets']=['plant','zombie','plant2','zombie2']
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_original',cell=[8,6],name='坚果')]
        c['operations'] += [dict(op='fume_line',unit=0,center=[240.,400.],angle=(0.,180.,10.,-10.)[i//24],sourced=i%3!=0) for unused in range(2)]
        cases.append(('fume-line-'+str(i),c))
    for i in range(64):
        c=base();c['globals']['模式']='正常模式';c['damage'].update(until=2500,factor=(0.,.25,1.,2.)[i%4],cards={'producer':True})
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_write',plant=0,values={'植物血':(0.,1.,5.,50.)[i//4%4],'_pvp_card':'producer','_pvp_owner':'plant','_pvp_anchor_until':100. if i>=32 else 0.}),
            dict(op='lifecycle_hook',name='clear',fail_before=i%3==0,fail_after=i%3==1),dict(op='fume_damage_plant',plant=0,amount=(-2.,0.,1.,100.)[i//16])]
        cases.append(('fume-plant-protection-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['模式']='正常模式' if i%3 else '我是僵尸'
        c['operations']=[dict(op='lifecycle_hook',name='fume_player',fail_before=i%4==0,fail_after=i%4==1,body=[dict(op='source_observe')]),
            dict(op='fume_damage_player',direction=(-1.,0.,1.)[i//16]),dict(op='fume_damage_player',direction=1.)]
        cases.append(('fume-player-fallback-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][0]['魅惑']=None;c['damage']['hero_targets']=['plant','zombie']
        c['operations']=[dict(op='lifecycle_hook',name='fume_damage',fail_before=i%4==0,fail_after=i%4==1,
            body=[dict(op='roster_replace',targets=[3,2]),write(1,位置=[1200.,432.,0.,0.]),dict(op='source_observe')]),
            dict(op='fume_damage_unit',index=(0,1,5,99)[i//16],target=(1,'zombie')[i%2],amount=(1.,30.,1000.,-2.)[i//4%4]),
            dict(op='fume_line',unit=0,center=[240.,400.],angle=0.)]
        cases.append(('fume-index-fallback-'+str(i),c))
    for i in range(80):
        c=base();c['services']['units'][0]['魅惑']=None;c['globals']['秘籍']=['雷霆'];c['services']['units'][1].update(手持='钢门',手持血量=10000.)
        c['fume']['units'][0].update(射=(0.,1.,73.,74.,90.,99.,100.,120.)[i%8],植物僵尸发射动画=(0.,1.,50.,None,-1.)[i//16],
            **{P+'fumeshroom_zombie_cd':5.,P+'fumeshroom_zombie_attack_angle':(None,0.,180.,45.)[i//8%4],P+'fumeshroom_zombie_damage_done':(None,0.,1.,5.)[i//8%4]})
        cfg=({'fire_anim':None,'damage_tick':None,'damage_pulses':None,'visual_tick':None},{'fire_anim':5.,'damage_tick':1.,'damage_pulses':3.,'visual_tick':1.},{'missing':['fire_anim','damage_tick','damage_pulses','visual_tick']},{'damage_tick':-1.,'visual_tick':1000.,'damage_pulses':1.})[i%4]
        cfg['visual_bubbles']=2.
        c['operations']=[dict(op='fume_shoot_tick',unit=0,config=cfg)]+[dict(op='fume_animate',unit=0,config=cfg) for unused in range(4)]
        cases.append(('fume-pulse-'+str(i),c))
    for i in range(48):
        c=base();c['fume']['units'][0][P+'fumeshroom_zombie_cd']=(None,0.,1.,2.,-1.,4.)[i%6]
        c['services']['units'][0]['植物僵尸角']=(None,0.,90.,180.)[i%4]
        if i%2:c['services']['units'][0]['魅惑']=None
        c['operations']=[dict(op='fume_update',unit=0,sourced=i%3!=0,config={'fire_anim':5.,'damage_tick':2.,'visual_tick':1.,'visual_bubbles':1.}) for unused in range(9)]
        cases.append(('fume-update-'+str(i),c))
    for i in range(48):
        c=base();c['operations']=[dict(op='fume_environment',time=(0.,1.,10.)[i%3],width=(None,100.,960.)[i%3],height=576.),
            dict(op='fume_bubbles',center=[240.,400.],angle=(0.,45.,180.,270.)[i%4],blue=i%2==0,
                 config={'visual_bubbles':(None,0.,1.,36.,601.,1201.)[i//8],'attack_length':(None,-1.,.5,6.)[i%4]})]
        c['operations'] += [dict(op='fume_bubble_tick',time=t) for t in (0.,1.,1.005,1.006,1.0166666666666666,1.0416666666666667,1.2,1.21,2.,10.)]
        cases.append(('fume-bubbles-'+str(i),c))
    return cases
