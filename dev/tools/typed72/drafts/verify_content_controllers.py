"""Concrete September, PvP56, PvP70 and barrel controllers in the content gate chain."""
import ast
import copy
import dis
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('controller_content_reference',HERE/'verify_content_zombies.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
shared=base.shared;hero=base.hero;shooting=base.shooting
S56=shared.PVP/'pvp56_zombies.py';S70=shared.LOCAL/'pvp70_content.py'
BARRELS=shared.PVP/'native_barrels.py';CAT70=shared.PVP/'pvp70_catalog.py'
FIELDS=('_pvp_dance_owner','_pvp_zs_dance_parent','_pvp_squad_owner','_pvp_dance_slot','_pvp_dance_saved_speed',
        '_pvp_dance_clock','_pvp_dance_rate','_pvp_dancing','_pvp_dance_impulse','_pvp_dance_side',
        '_pvp70_clock','_pvp_reaper_idle','_pvp_airdrop_used','_pvp_bone_grave','_pvp_hook_pull','_pvp_barrel_position')


def reference():
    ref=base.reference();env=dict(math=math,copy=copy,types=types,sys=sys,dis=dis,__package__=shared.PACKAGE)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    shooting.projectiles.functions(shared.PVP/'teams.py',['team_of'],env)
    equipment=types.ModuleType(shared.PACKAGE+'.zombie_secrets')
    shooting.projectiles.functions(shared.LOCAL/'zombie_secrets.py',['hand_kind'],equipment.__dict__)
    sys.modules[equipment.__name__]=equipment
    env['BLACK_ZOMBIES']=hero.constant(shared.PVP/'expansion_catalog.py','BLACK_ZOMBIES')
    hero.selected_class(base.SOURCE,['bite_damage','plant_bite'],'ContentBites',env)
    e56=dict(env)
    for key in ('NAMES','DANCE_SLOTS','DANCE_TICKS'):e56[key]=hero.constant(S56,key)
    hero.selected_class(S56,['configure','alive','action_rate','children','wild_children','wild','release','leader_for','anchor',
        'before_tick','zombie_gate','finish_zombie','fill_group','_deferred_dancer','spawn_squad','_deferred_sled'],'Z56',e56)
    e70=dict(env)
    for key in ('HOOK','REAPER','HEAD','BASIN','GRABBER','LETTUCE','ANCHOR_SECRET','AIRDROP_SECRET'):e70[key]=hero.constant(CAT70,key)
    shooting.projectiles.functions(S70,['alive','factor'],e70)
    hero.selected_class(S70,['is_head','invulnerable','configure','seat_has','zombie_gate','airdrop','airdrop_child',
        'hook_target','snapshot','hook','graves','grave_at','grave_cell','bone_cell','throw_bone','reflect','wind',
        'impact_bone','projectiles','segment_hit'],'Z70',e70)
    es=dict(env);es['TRACKING_KEYS']=sys.modules[shared.PACKAGE+'.native_physics'].TRACKING_KEYS
    hero.selected_class(shared.SEPTEMBER,['targetable','chase_goal','zombie_gate','wave_chase','finish_zombie'],'September',es)
    eb=dict(env)
    hero.selected_class(BARRELS,['__init__','track','detach','reconcile','contact_plants','float_on_water','correct_pair','tick'],'Barrels',eb)
    hero.selected_class(base.SOURCE,['break_barrel','barrel_active','barrel_overlap','move_barrel'],'ContentBarrels',eb)
    tree=ast.parse(base.SOURCE.read_text(encoding='utf8'))
    install,=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_install']
    start,=[i for i,node in enumerate(install.body) if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='displacement' for t in node.targets)]
    end,=[i for i,node in enumerate(install.body) if isinstance(node,ast.Assign)
          and any(isinstance(t,ast.Attribute) and t.attr=='barrel_displacement' for t in node.targets)]
    eb['displacement_install']=compile(ast.Module(body=install.body[start:end+1],type_ignores=[]),str(base.SOURCE),'exec')
    eb['inject_iteration_gate']=importlib.import_module(shared.PACKAGE+'.native_gate').inject_iteration_gate
    ref.update(controller56=e56,controller70=e70,controller_september=es,controller_barrels=eb,controller_bites=env)
    return ref


class ContentControllersExtension(base.ContentZombiesExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;g=self.g;r=self.controller
        self.controllers_seen=False;self.controller_events=[];self.factory_events=[];self.wild_dance=False;self.orphan_sequence=0
        self.z56=ref['controller56']['Z56']();self.z70=ref['controller70']['Z70']();self.september=ref['controller_september']['September']()
        for obj in (self.z56,self.z70,self.september):obj.c=r;obj.b=b;obj.g=g
        self.september.paths={};self.z70.shots=[]
        self.barrels=ref['controller_barrels']['Barrels'](r)
        for key,method in ref['controller_bites']['ContentBites'].__dict__.items():
            if callable(method):setattr(r,key,types.MethodType(method,r))
        bite=r.bite_damage
        def observed_bite(unit,target):self.event('bite',unit,self.content_label(target));return bite(unit,target)
        r.bite_damage=observed_bite
        # Restore the real fixed-speed secret policy replaced by the boundary
        # fixture in the base gate/finish verifier.
        b.zsecrets.movement_factor=types.MethodType(ref['actions']['Secrets'].movement_factor,b.zsecrets)
        for key,method in ref['controller_barrels']['ContentBarrels'].__dict__.items():
            if callable(method):setattr(r,key,types.MethodType(method,r))
        local=dict(ref['controller_barrels'],self=r,b=b,g=g)
        exec(local['displacement_install'],local)
        def observed(name,method):
            def callback(unit,*args):self.event(name,unit,*args);return method(unit,*args)
            return callback
        # Keep the already bound entity-phase/maintenance/economy methods on
        # this same controller. Replacing it drops hide_ghost_cells and its
        # state before a full NativeTick reaches those otherwise real phases.
        r.september.targetable=self.september.targetable
        r.september.zombie_gate=observed('september_gate',self.september.zombie_gate)
        r.september.wave_chase=observed('wave_chase',self.september.wave_chase)
        r.september.finish_zombie=observed('september_finish',self.september.finish_zombie)
        r.zombies56=types.SimpleNamespace(zombie_gate=observed('zombies56_gate',self.z56.zombie_gate),
            finish_zombie=observed('zombies56_finish',self.z56.finish_zombie))
        r.pvp70=self.z70;r.pvp70.zombie_gate=observed('zombies70_gate',self.z70.zombie_gate)
        r.barrels.correct_pair=observed('barrel_correct',self.barrels.correct_pair)
        r.barrels.detach=observed('barrel_detach',self.barrels.detach)
        r.barrels.contact_plants=observed('barrel_contact',self.barrels.contact_plants)
        r.barrels.float_on_water=self.barrels.float_on_water
        r.break_barrel=observed('barrel_break',r.break_barrel);r.move_barrel=observed('barrel_move',r.move_barrel)
        # Internal calls from the literal barrel class go through those same
        # installed NativeContent wrappers, as they do in the production chain.
        r.pvp64.gravity=4*g['plk'];r.pvp64.umbrella_reflect=self.grenadiers.umbrella_reflect
        b.zsecrets.hide_plants=lambda unit:self.event('hide_headhunt',unit)
        b.zsecrets.has=lambda name:self.wild_dance if name=='狂野舞步' else False
        self.z70.draw_effects=lambda:self.factory_events.append(['effects70'])
        self.barrels.crush_plant=lambda unit,plant:self.crush(unit,plant)
        def remnant(x,y,source):
            self.factory_events.append(['bone_grave',round(y/b.tile)-1,int(x//b.tile),source.get('_pvp_id'),source.get('方向',1)])
            self.before('bone_grave_factory');self.after('bone_grave_factory');return None
        b.spawn_remnant=remnant
        def spawn_plant(name,row,col,facing,**kwargs):
            self.factory_events.append(['bone_gravebuster',row,col,facing,self.pending_bone_source])
            self.before('bone_gravebuster_factory');self.after('bone_gravebuster_factory');return []
        b.engine.spawn_plant=spawn_plant;b._plant_native_factory=None;self.pending_bone_source=None
        impact=self.z70.impact_bone
        def impact_bone(shot,row,col):self.pending_bone_source=shot['source'];return impact(shot,row,col)
        self.z70.impact_bone=impact_bone
        card=b._unit_card
        b._unit_card=lambda side,key:dict(id=key) if key=='zombie:滚桶僵尸' else card(side,key)
        def register(unit,card,owner,free,parent):
            self.orphan_sequence+=1;uid='barrel:'+str(self.orphan_sequence)
            unit.update(_pvp_id=uid,_pvp_owner=owner,_pvp_card=card['id']);b._native_objects[uid]=unit;self.units.append(unit)
            self.factory_events.append(['register_barrel',self.label(unit),parent.get('id')]);self.before('barrel_register');self.after('barrel_register')
        b._register=register
        emit=b._emit
        def event(name,**fields):
            if name in ('dance_started','reaper_idle','reaper_resumed','airdrop_summon','hook_fired','bone_thrown',
                        'projectile_reflected','bone_grave','bone_gravebuster','hook_hit','barrel_detached','barrel_position_corrected') or (name=='content_summon' and 'slot' in fields):
                self.controller_events.append([name,fields]);self.before('controller_event');self.after('controller_event')
            elif name=='grenade_reflected':
                self.controller_events.append([name,fields]);self.before('controller_event');self.after('controller_event')
            else:emit(name,**fields)
        b._emit=event

    def crush(self,unit,plant):
        self.factory_events.append(['crush',self.label(unit),self.content_label(plant)])
        self.before('barrel_crush');self.after('barrel_crush')

    def operation(self,op):
        name=op['op']
        if name=='controllers_setup':self.controllers_seen=True;self.wild_dance=op.get('wild',False)
        elif name=='controller_fields':self.units[op['unit']].update(copy.deepcopy(op['fields']))
        elif name=='controller56_configure':
            self.b.patch.ns['__pvz_sb_K_ZOMBIE_OBSERVED_MAX_HP']='__pvz_sb_zombie_observed_max_hp'
            return self.z56.configure(self.units[op['unit']],dict(content=op['name'],native_hp=op['hp']))
        elif name=='controller70_configure':return self.z70.configure(self.units[op['unit']],dict(content=op['name']))
        elif name=='controller56_before':self.z56.before_tick()
        elif name=='controller70_projectiles':self.z70.projectiles()
        elif name=='controller_plant_registry':self.b._native_objects[op['id']]=self.all_plants[op['plant']]
        elif name=='barrel_track':self.barrels.track(self.units[op['unit']])
        elif name=='barrel_tick':self.barrels.tick()
        elif name=='barrel_reconcile':self.barrels.reconcile()
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.controllers_seen:return
        records=[{key:unit[key] for key in FIELDS if key in unit} for unit in self.units]
        for unit in records:
            if '_pvp_hook_pull' in unit:unit['_pvp_hook_pull']=list(unit['_pvp_hook_pull'])
        shots=copy.deepcopy(self.z70.shots)
        for shot in shots:
            if 'cell' in shot:shot['cell']=list(shot['cell'])
        row['controllers']=dict(events=self.controller_events,factory=self.factory_events,
            units=records,shots=shots,carriers=[self.label(unit) for unit in self.barrels.carriers])


def paths():
    return base.paths()+[Path(__file__).resolve(),S56,S70,BARRELS,CAT70,shared.SEPTEMBER,
        shared.PVP/'native_gate.py',shared.LOCAL/'zombie_secrets.py',HERE/'content_controllers_probe.cpp']


def cases():
    prototype=base.cases()[0][1];result=[]
    black_bite_node,=[node for node in ast.parse(hero.TARGETS.read_text(encoding='utf8')).body
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='BLACK_BITE_VARIANTS' for target in node.targets)]
    black_bites=list(ast.literal_eval(black_bite_node.value.args[0]))
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1260000+i
        ops=case['operations']=case['operations'][:21]
        black=list(hero.constant(shared.PVP/'expansion_catalog.py','BLACK_ZOMBIES'))
        ops.append(dict(op='controllers_setup',wild=i%2==1,black=black,black_bites=black_bites))
        return case,ops
    def fields(ops,unit=0,**value):ops.append(dict(op='controller_fields',unit=unit,fields=value))
    def cycle(ops):ops.extend([dict(op='content_gate',unit=0),dict(op='content_finish')])
    for i in range(8):
        case,ops=setup(i)
        fields(ops,_pvp_content='雪人僵尸' if i%2==0 else '垃圾桶僵尸',手持='钢门',手持血量=100.,位置=[264.,432.,0.,0.])
        if i%4==2:ops.append(dict(op='content_orders',command='follow',commands={}))
        if i%4==3:fields(ops,_pvp_zs_headhunt=True)
        ops += [dict(op='plant_original',name='向日葵',cell=[8,7],facing=1.),dict(op='plant_fields',plant=0,fields={'_pvp_id':'target-plant','植物血':100.},erase=['睡觉'])]
        cycle(ops);cycle(ops);result.append(('concrete-september-yeti-and-equipment-'+str(i),case))
    for i in range(8):
        case,ops=setup(20+i)
        ops.append(dict(op='controller56_configure',unit=0,name='舞王僵尸',hp=160.));fields(ops,_pvp_dance_clock=999.)
        if i%4==1:fields(ops,冰冻=1001.)
        if i%4==2:fields(ops,魅惑=200.)
        if i%4==3:ops.append(dict(op='zombie64_spawn_mode',value='none'))
        ops.append(dict(op='zombie64_registry',unit=0,id='body-0'));cycle(ops);ops.append(dict(op='controller56_before'));cycle(ops)
        result.append(('concrete-dance-clock-group-and-allegiance-'+str(i),case))
    for i in range(8):
        case,ops=setup(40+i)
        fields(ops,_pvp_content='滚桶僵尸',手持='滚桶',手持血量=400.,_pvp_barrel_direction=1.,
            _pvp_barrel_position=[(300.,650.)[i%2],432.,0.,0.],位置=[264.,432.,0.,0.])
        ops.append(dict(op='barrel_track',unit=0))
        if i%4==1:fields(ops,血量=0.)
        if i%4==2:fields(ops,魅惑=250.)
        if i%4==3:fields(ops,手持血量=0.)
        cycle(ops);ops.append(dict(op='barrel_tick'));result.append(('concrete-barrel-identity-detach-break-and-gravity-'+str(i),case))
    for i in range(8):
        case,ops=setup(60+i)
        name='钩索僵尸' if i%2==0 else '死神僵尸'
        ops.append(dict(op='controller70_configure',unit=0,name=name));fields(ops,_pvp70_clock=1499.,出场=500.)
        ops.append(dict(op='zombie64_registry',unit=0,id='body-0'))
        ops += [dict(op='plant_original',name='向日葵',cell=[8,5],facing=1.),
                dict(op='plant_fields',plant=0,fields={'_pvp_id':'target-plant','植物血':100.},erase=['睡觉']),
                dict(op='controller_plant_registry',plant=0,id='target-plant')]
        if i%4==2:fields(ops,冰冻=1001.)
        if i%4==3:ops.append(dict(op='poison_clock',tick=5000))
        cycle(ops)
        for unused in range(6):ops.append(dict(op='controller70_projectiles'))
        result.append(('concrete-hook-reaper-clock-and-live-projectiles-'+str(i),case))
    return result


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,ContentControllersExtension,'typed72-content-controller-composition',probe_timeout=600))
