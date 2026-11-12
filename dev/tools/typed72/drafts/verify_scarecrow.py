"""Literal scarecrow aura, suspended-grave navigation, hopping and crow echo."""
import contextlib
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_reed_plants as reeds
flying=reeds.flying
shared=reeds.shared
shooting=reeds.shooting
hero=reeds.hero
SOURCE=reeds.SOURCE
CATALOG=reeds.CATALOG


def reference():
    ref=reeds.reference();env=dict(ref['reed_plants'],contextmanager=contextlib.contextmanager)
    for key in ('SCARECROW_SLOW','SCARECROW_AURA_CELLS','CROW_DAMAGE'):env[key]=hero.constant(CATALOG,key)
    env['HOP_PERIOD']=hero.constant(SOURCE,'HOP_PERIOD')
    hero.selected_class(SOURCE,['configure','scarecrows','aura_cells','slow_factor','grave_goal','scarecrow_step','crow_echo'],'Scarecrows',env)
    hero.selected_class(shared.BATTLE,['_ban_free_spawn'],'SpawnScope',env)
    ref['scarecrows']=env
    return ref


class ScarecrowExtension(flying.FlyingPlantsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['scarecrows'];r=self.scarecrows=env['Scarecrows']();r.b=self.b;r.g=self.g;r.c=self.content
        b=self.b;b._spawn_ban_exempt=0;b._suspended_graves=[]
        b._ban_free_spawn=types.MethodType(env['SpawnScope']._ban_free_spawn,b)
        self.scarecrow_seen=False;self.crow_calls=[];self.crow_events=[];self.crow_child=None
        def spawn(card,owner,x,y,facing,free,parent):
            self.crow_calls.append([card,owner,x,y,facing,free,parent,b._spawn_ban_exempt])
            self.before('crow_spawn');self.after('crow_spawn')
            return dict(id=self.crow_child) if self.crow_child is not None else None
        b.spawn=spawn
        original=b._emit
        def emit(event_type,**fields):
            if event_type=='crow_echo':
                self.crow_events.append([event_type,fields]);self.before('crow_event');self.after('crow_event')
            else:original(event_type,**fields)
        b._emit=emit

    def operation(self,op):
        name=op['op'];r=self.scarecrows;b=self.b
        if name=='scarecrow_setup':self.scarecrow_seen=True;self.crow_child=op['child'];b._spawn_ban_exempt=op.get('exempt',0)
        elif name=='scarecrow_suspended':b._suspended_graves=[self.units[i] for i in op['units']]
        elif name=='scarecrow_fields':self.units[op['unit']].update(copy.deepcopy(op['fields']))
        elif name=='scarecrow_configure':return r.configure(self.units[op['unit']],dict(content=op['name'],hp=op['hp']))
        elif name=='scarecrow_living':return [self.label(unit) for unit in r.scarecrows()]
        elif name=='scarecrow_aura':return [list(cell) for cell in sorted(r.aura_cells())]
        elif name=='scarecrow_slow':return r.slow_factor(self.all_plants[op['plant']],r.aura_cells())
        elif name in ('scarecrow_goal','scarecrow_step','crow_echo'):
            try:
                if name=='scarecrow_goal':return self.content_label(r.grave_goal(self.units[op['unit']]))
                if name=='scarecrow_step':r.scarecrow_step(self.units[op['unit']],op['factor'])
                else:
                    child=r.crow_echo(dict(x=op['point'][0],y=op['point'][1],id=op['id']))
                    return child['id'] if child is not None else None
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.scarecrow_seen:row['scarecrows']=dict(calls=self.crow_calls,events=self.crow_events,exempt=self.b._spawn_ban_exempt,
            units=[{key:unit[key] for key in ('_pvp_base_speed','_pvp_walk_speed','_pvp_hop_clock','_pvp_flight','移速','_pvp_max_hp',
                                            '_pvp_bite_plant','_pvp_no_attack','_pvp_no_hero_attack','_pvp_content') if key in unit} for unit in self.units])


def cases():
    output=[];prototype=flying.plants.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1000000+i
        ops=case['operations']=case['operations'][:2]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        solid=[[0]*20 for unused in case['plant_world']['grid']];solid[9]=[1]*20
        ops.extend([dict(op='flying_setup',height=len(case['plant_world']['grid'])*48.),dict(op='flying_published',solid=solid),
                    dict(op='scarecrow_setup',child='echo-child',exempt=i%3),dict(op='plant_original',name='杨桃',cell=[8,5],facing=1.),
                    dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉'])])
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_owner':'zombie','血量':100.,'大小':2.,
                '位置':[240.+unit*96.,432.,0.,0.],'手持':'','手持血量':0.,'防具':'','防具血量':0.},erase=['魅惑']))
            ops.append(dict(op='scarecrow_fields',unit=unit,fields={'移速':.6,'_pvp_grave':unit>0}))
            ops.append(dict(op='source_write',unit_source=unit,values={'_pvp_id':'crow-'+str(3-unit)}))
        ops.append(dict(op='scarecrow_configure',unit=0,name='稻草人',hp=100.))
        return case,ops,solid
    for i in range(64):
        case,ops,solid=setup(i)
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[(0.,959.999,-.001,960.)[i%4],(0.,23.999,24.,456.)[i//4%4],0.,0.]}))
        ops.append(dict(op='plant_fields',plant=0,fields={'坐标':[(0,0,0,8)[i//4%4],(0,19,19,0)[i%4]]}))
        if i//16==1:ops.append(dict(op='plant_unit',unit=0,fields={'魅惑':None}))
        if i//16==2:ops.append(dict(op='plant_unit',unit=0,fields={'灰烬':0.}))
        if i//16==3:ops.append(dict(op='plant_unit',unit=0,fields={'血量':0.}))
        ops.extend([dict(op='scarecrow_living'),dict(op='scarecrow_aura'),dict(op='scarecrow_slow',plant=0),
                    dict(op='scarecrow_configure',unit=3,name='乌鸦',hp=70.)])
        output.append(('scarecrow-config-aura-seams-and-control-'+str(i),case))
    for i in range(64):
        case,ops,solid=setup(100+i)
        for unit,x in ((1,144.),(2,336.)):
            ops.append(dict(op='plant_unit',unit=unit,fields={'位置':[x,432.,0.,0.]}))
        ops.append(dict(op='roster_replace',targets=[0,1,1] if i%2 else [0,1,2]))
        ops.append(dict(op='scarecrow_suspended',units=[1,2,3,2]))
        if i//4%4==1:ops.append(dict(op='plant_unit',unit=2,fields={'灰烬':None}))
        if i//4%4==2:ops.append(dict(op='plant_unit',unit=1,fields={'血量':0.}))
        if i//4%4==3:ops.append(dict(op='plant_unit',unit=0,fields={'魅惑':0.}))
        if i//16==1:ops.append(dict(op='source_write',unit_source=1,values={'_pvp_id':None}))
        if i//16==2:
            for unit in (1,2):ops.append(dict(op='source_write',unit_source=unit,values={'_pvp_id':None}))
        if i//16==3:ops.append(dict(op='source_write',unit_source=2,values={'_pvp_owner':'plant'}))
        ops.extend([dict(op='scarecrow_goal',unit=0,catch=True),dict(op='scarecrow_step',unit=0,factor=.5,catch=True)])
        output.append(('scarecrow-live-suspended-graves-id-ties-'+str(i),case))
    for i in range(96):
        case,ops,solid=setup(200+i)
        for unit in (2,3):ops.append(dict(op='plant_unit',unit=unit,fields={'血量':0.}))
        ops.append(dict(op='plant_unit',unit=1,fields={'位置':[(240.,297.6,297.600001,144.,936.,0.)[i%6],432.,0.,0.]}))
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[240.,432.,6.,(0.,.0288,.02880001,-.0288)[i//6%4]]}))
        ops.append(dict(op='scarecrow_fields',unit=0,fields={'_pvp_hop_clock':(0.,228.,229.,230.)[i//24],
                                                          '_pvp_walk_speed':(.6,100.)[i%2]}))
        if i//8%3==1:solid[8][4]=solid[8][5]=solid[8][6]=1
        if i//8%3==2:solid[8][4]=solid[8][5]=solid[8][6]=1;solid[7][5]=1
        ops.extend([dict(op='flying_published',solid=solid),dict(op='scarecrow_step',unit=0,factor=(0.,.5,1.)[i%3]),
                    dict(op='scarecrow_step',unit=0,factor=1.)])
        output.append(('scarecrow-ground-jitter-walls-hop-and-momentum-'+str(i),case))
    for i in range(32):
        case,ops,solid=setup(400+i)
        for unit in (1,2,3):ops.append(dict(op='scarecrow_configure',unit=unit,name='稻草人',hp=100.))
        if i%4==1:ops.append(dict(op='plant_unit',unit=3,fields={'魅惑':0.}))
        if i%4==2:ops.append(dict(op='scarecrow_setup',child=None,exempt=2))
        if i%4==3:ops.append(dict(op='roster_replace',targets=[]))
        hook='crow_spawn' if i%2 else 'crow_event'
        ops.append(dict(op='lifecycle_hook',name=hook,fail_before=i//4%4==0,fail_after=i//4%4==1,
                        body=[dict(op='roster_replace',targets=[0]),dict(op='source_write',unit_source=3,values={'_pvp_id':'changed'})]))
        ops.extend([dict(op='crow_echo',point=[240.,432.],id='deployed',catch=True),
                    dict(op='crow_echo',point=[240.,432.],id='deployed-2',catch=True)])
        output.append(('crow-echo-farthest-allegiance-and-scope-unwind-'+str(i),case))
    for i in range(24):
        case,ops,solid=setup(500+i)
        if i%3==0:ops.append(dict(op='roster_replace',targets=[0]))
        body=[]
        for tick in range(480):body.extend([dict(op='clock',tick=tick,time=tick/250.),dict(op='scarecrow_step',unit=0,factor=(0.,.5,1.)[i%3])])
        ops.append(dict(op='batch',body=body));ops.append(dict(op='scarecrow_aura'))
        output.append(('scarecrow-continuous-clock-and-grave-chase-'+str(i),case))
    return output


def paths():
    return reeds.paths()+[Path(__file__).resolve(),Path(reeds.__file__),shared.ROOT/'tools/typed72/scarecrow_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,ScarecrowExtension,'typed72-scarecrow',probe_timeout=600))
