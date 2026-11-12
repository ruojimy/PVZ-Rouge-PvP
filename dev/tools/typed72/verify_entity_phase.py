"""Run the installed owner loop, source charts, visibility and original entities wordcode."""
import ast
import contextlib
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_world_rules as shared

hero=shared.hero
shooting=shared.shooting
PACKAGE=shared.PACKAGE
PVP=shared.PVP
LOCAL=shared.LOCAL
PERIODIC=PVP/'native_periodic_targets.py'
EXPANSION=PVP/'native_expansion.py'
TARGETS=LOCAL/'native_targets.py'

def reference():
    ref=shared.reference()
    env=dict(math=math,__package__=PACKAGE,contextmanager=contextlib.contextmanager,nullcontext=contextlib.nullcontext)
    env['team_of']=lambda s:'plant' if s.startswith('plant') else 'zombie'
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    targetmod=types.ModuleType(PACKAGE+'.native_targets')
    targetmod._COMBAT_HERO_KEYS=hero.constant(TARGETS,'_COMBAT_HERO_KEYS')
    sys.modules[targetmod.__name__]=targetmod
    names=['_plant_switching','_set_alias','_nearest_plant_seat','_switch_plant','_switch_back','_tracking_index',
           '_hero_lock','_tracking_gate','_petrified_torch_ignite_plant_peas']
    env['battle']=hero.selected_class(shared.BATTLE,names,'RegionBattle',env)
    env['simulation']=hero.selected_class(shooting.projectiles.SIMULATION,['team_seats','distance','_solid','cell','line_of_sight'],'Sight',env)
    env['index']=hero.selected_class(TARGETS,['target_index'],'Index',env).target_index
    env['chart']=hero.selected_class(PERIODIC,['begin','restore'],'Chart',env)
    env['source']=hero.selected_class(EXPANSION,['source_gate','restore_art','alias_art'],'Source',env)
    env['september']=hero.selected_class(shared.SEPTEMBER,['targetable','hide_ghost_cells'],'HiddenCells',env)
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    start=ast.dump(ast.parse("self.targets.target_index(self.engine.regions['unit_target_index'])").body[0])
    end=ast.dump(ast.parse("self.g['实体']=completed").body[0])
    sequences=[]
    for fn in ast.walk(tree):
        if not isinstance(fn,ast.FunctionDef):continue
        matches=[i for i,n in enumerate(fn.body) if ast.dump(n)==end]
        if not matches:continue
        last,=matches
        first=max(i for i,n in enumerate(fn.body[:last]) if ast.dump(n)==start)
        sequences.append(fn.body[first:last+1])
    body,=sequences
    env['phase']=compile(ast.Module(body=body,type_ignores=[]),str(shared.BATTLE),'exec')
    ref['entity_phase']=env
    return ref

class PhaseExtension(shared.WorldRulesExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.phase_ref=ref['entity_phase'];self.track_seen=False
        b=self.b;g=self.g;env=self.phase_ref
        for cls in (env['battle'],env['simulation']):
            for method,fn in cls.__dict__.items():
                if callable(fn):setattr(b,method,types.MethodType(fn,b))
        self.c.target_index=types.MethodType(env['index'],self.c);self.c.hero_lock=b._hero_lock
        b.periodic_targets=env['chart']();b.periodic_targets.b=b;b.periodic_targets.shifted=[]
        b.periodic_targets.indexes=None;b.periodic_targets.active=False
        b.expansion=env['source']();b.expansion.b=b;b.expansion.g=g
        b.expansion.saved_atlas={};b.expansion.saved_rows=None
        b._alias_seat='plant';b._switch_state=None;b.torches=self.torches;b.plant_zombies=self.pz
        b.engine.regions['unit_target_index']=ref['world_rules']['target_code']
        b.engine.execute=lambda name:exec(b.engine.regions[name],g)
        b.content=self.content;b.content.september=env['september']();b.content.september.g=g
        b.content.release_pending_destination=lambda:self.render_log.append(['release_destination'])
        g['_pvp_entity_gate']=b._tracking_gate

    def operation(self,op):
        name=op['op'];g=self.g;b=self.b
        if name=='track_setup':
            self.track_seen=True;g['同横尸']=dict(copy.deepcopy(op['rows']));g['同竖尸']=dict(copy.deepcopy(op['cols']))
            g['分梯']=[];g['离玩家最近']=-1;g['最近距离']=op.get('distance',-1.)
            b.seats={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],
                     'pve':['plant'],'coop':['plant','plant2']}[op.get('mode','duel')]
            b.map={'tiles':[[{'solid':bool(v)} for v in row] for row in op['solid']]};b.rules['hero_lock_range']=360.
            for seat,(x,y,h,marked) in op['players'].items():b.players[seat].update(x=x,y=y,h=h,marked_until=marked)
            b._multi_plant=len(b.team_seats('plant'))>1
            for key in op.get('assets',[]):g['图集'].setdefault(key,self.surface(key))
            g.update(开车=0.,水='水')
        elif name=='track_unit':
            u=self.units[op['unit']]
            for key,field in [('entry','出场'),('split','分兵'),('hand','手持'),('owner','_pvp_owner')]:
                if key in op:u[field]=op[key]
        elif name=='pz_fume':
            return self.ns[shared.P+'damage_zombie_from_fumeshroom'](g,op['index'],g['僵尸'][op['index']],op['amount'],op['direction'])
        elif name=='doom_targets':
            return self.ns[shared.P+'doom_zombie_ash_targets'](g,self.units[op['unit']],*op['point'],op.get('scale',g['比']))
        elif name=='phase_run':
            exec(self.phase_ref['phase'],dict(self.phase_ref,self=b,prof=None))
        elif name in ('track_begin','track_index','track_lock','track_restore'):
            obj=self.births[op['entity']] if 'entity' in op else self.all_plants[op['plant']] if 'plant' in op else None
            if name=='track_begin':b.periodic_targets.begin(obj)
            elif name=='track_restore':b.periodic_targets.restore()
            elif name=='track_index':self.c.target_index(b.engine.regions['unit_target_index'],obj)
            else:return b._hero_lock(obj,op['side'])
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.track_seen:
            g=self.g;row['tracking']=[[[k,v] for k,v in g['同横尸'].items()],[[k,v] for k,v in g['同竖尸'].items()],
                                     g['分梯'],g['离玩家最近'],g['最近距离'],self.b.periodic_targets.active]

def cases():
    prototype=shared.cases()[0][1];out=[];entity=shared.peas.entity
    def setup(i):
        c=copy.deepcopy(prototype);c['seed']=91400+i;c['operations']=[]
        c['world_rules'].update(rage=False,deathmatch=False,dense=i%4==0)
        for seat,x in [('plant',40.),('plant2',905.),('zombie',935.),('zombie2',125.)]:
            c['heroes'][seat]['玩家位置'][:2]=[x,350.]
        c['globals']['玩家位置']=[120.,350.,0.,0.]
        grid=[[0]*20 for _ in c['plant_world']['grid']]
        if i%3==2:
            for row in grid:row[0]=1
        players={seat:[v['玩家位置'][0],v['玩家位置'][1],96.,10. if i%4==0 else 0.] for seat,v in c['heroes'].items()}
        c['operations'].append(dict(op='track_setup',solid=grid,players=players,rows=[[3,[0,1,19,10]],[1,[7,-3]]],
                                    cols=[[0,[1]],[20,[3,5]],[19,[4]],[-1,[7]]],mode=('duel','duo','pve','coop')[i%4],
                                    assets=['爆炸','蓝泡泡','爆炸-受伤','蓝泡泡-受伤']))
        for j in range(4):
            c['operations']+=[shooting.write(j,位置=[(10.,938.,120.,240.)[j],350.+j,0.,0.]),
                              dict(op='track_unit',unit=j,entry=(0 if i%5==0 and j==2 else 500),
                                   hand='梯子' if j==2 else '',split=0,owner=('plant' if j==3 else 'zombie'))]
        return c
    for i in range(48):
        c=setup(i);ops=c['operations'];ops+=[dict(op='roster_replace',targets=[0,1,2,3,'plant','zombie','zombie2']),
            entity((10.+i,320.,1.,0.),'尖刺'),dict(op='region_fields',entity=0,values={'_pvp_cattail':True,'_pvp_owner':'plant'})]
        ops += [dict(op='track_lock',entity=0,side=s) for s in ('plant','zombie','zombie2')]
        ops += [dict(op='track_index'),dict(op='track_begin',entity=0),dict(op='track_index',entity=0)]
        if i%2:ops.append(shooting.write(1,位置=[-28.,340.,-1.,0.]))
        ops += [dict(op='track_restore'),dict(op='track_index')]
        out.append(('source-chart-'+str(i),c))
    for i in range(72):
        c=setup(i);ops=c['operations'];ops += [dict(op='roster_replace',targets=[0,1,2,3,'zombie'])]
        for j in range(5):
            owner=('zombie','plant',None,'zombie','plant2')[j]
            v={'消亡':(0,1024,1023)[(i+j)%3],'_pvp_art_name':'蓝泡泡'}
            if owner:v['_pvp_owner']=owner
            if j==1:v.update(追踪=1,_pvp_cattail=True)
            ops += [entity(((35.,920.,815.,50.,470.)[j],320.,1.,0.),'爆炸',1 if j%2 else -1),dict(op='region_fields',entity=j,values=v)]
        if i%3==1:ops += [dict(op='squash_roster',entities=[4,2,1,3,0,0])]
        ops += [dict(op='phase_run') for _ in range(3)]
        out.append(('entity-owner-pass-'+str(i),c))
    for i in range(48):
        c=setup(i);ops=c['operations']
        center=(240.,400.)
        for j in range(3):
            ops.append(shooting.write(j,位置=[240.+j*32.,400.,0.,0.],方向=1.))
        c['heroes']['plant']['玩家位置'][:2]=[265.,408.]
        c['heroes']['zombie']['玩家位置'][:2]=[290.,412.]
        if i%2:c['services']['units'][0]['魅惑']=0.
        ops += [dict(op='roster_replace',targets=([0,1,2,'plant','zombie'],[0,2],['plant','zombie',0,1])[i%3]),
                dict(op='squash_pick',unit=0),dict(op='squash_spawn',unit=0,held=0,sourced=True),
                dict(op='squash_enemy',entity=0),dict(op='squash_hit',entity=0,impact_x=center[0],sourced=True)]
        out.append(('installed-squash-'+str(i),c))
    for i in range(36):
        c=setup(i);ops=c['operations']
        c['heroes']['plant']['玩家位置'][:2]=[250.,400.]
        c['heroes']['zombie']['玩家位置'][:2]=[280.,400.]
        if i%2:c['services']['units'][0]['魅惑']=0.
        ops += [dict(op='roster_replace',targets=[0,1,'plant','zombie']),
                dict(op='chili_scope',target='plant' if i%2==0 else 'zombie',owner='zombie' if i%2==0 else 'plant',unit_source=0,phase='zombies',
                     body=[dict(op='pz_fume',index=i%4,direction=1.,amount=(1.,10.,20.)[i%3])]),
                dict(op='doom_targets',unit=0,point=[250.,370.],scale=48.)]
        out.append(('installed-fume-and-doom-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(shared.__file__),shared.ROOT/'tools/typed72/world_rules_probe.cpp',
           PERIODIC,EXPANSION,TARGETS,shared.TORCH,shared.PLANT_ZOMBIES,shared.VINES,shared.BATTLE,shared.SEPTEMBER,
           PVP/'native_physics.py',PVP/'native_runtime.py',PVP/'native_bytecode.py',PVP/'native_gate.py',LOCAL/'native_protection.py']
    sys.exit(shooting.main(paths,reference,cases,PhaseExtension,'typed72-owner-entity-phase'))
