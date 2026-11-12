"""Literal native driver with concrete original regions and observed outer-controller boundaries.

This checks composition order and continuous native state. Outer content and
presentation boundaries are explicit fixtures and do not establish a product.
"""
import ast
import contextlib
import copy
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_content_zombies64 as zombies
import verify_plant_maintenance as maintenance
import verify_grave_binding as binding
import verify_plant_utilities as utilities
import verify_seat_paths as paths_module
import verify_hero_phase as heroes
import verify_zombie_actions as actions
shared=zombies.shared
hero=zombies.hero
shooting=zombies.shooting


def reference():
    ref=zombies.reference()
    for module in (maintenance,binding,utilities,paths_module,heroes,actions):
        extra=module.reference()
        for key,value in extra.items():
            if key not in ref:ref[key]=value
    env=dict(ref['seat_phase'],nullcontext=contextlib.nullcontext)
    env['rest_factor']=ref['economy']['rest_factor']
    hero.selected_class(shared.BATTLE,['_step_original','_select_hero','zombie_hero_proxies'],'Driver',env)
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    fn,=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_step_original']
    start,=[i for i,node in enumerate(fn.body) if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='graves' for t in node.targets)]
    finish,=[i for i,node in enumerate(fn.body) if isinstance(node,ast.Expr)
             and ast.dump(node)==ast.dump(ast.parse('self.content.wind.after_zombies()').body[0])]
    env['zombie_phase']=compile(ast.Module(body=fn.body[start:finish],type_ignores=[]),str(shared.BATTLE),'exec')
    env['regions']={name:marshal.loads((shared.ROOT/('extract/live/'+name+'.marshal')).read_bytes())
                    for name in ('zombie_coordinates','zombie_body_index','particles')}
    ref['native_tick']=env
    return ref


# Observed bound of the real _draw_dave: the recovered dave_state region runs on the
# avatar's fields, HP on the source's 20-point scale. Alpha is presentation and is discarded.
DAVE_STATE=compile((Path(__file__).resolve().parents[3]/'extract/live/dave_state.py').read_text(encoding='utf8'),'dave_state','exec')
class _DaveImage:
    def set_alpha(self,value):pass
def dave_state_region(avatar):
    maximum=avatar.get('_pvp_max_hp',20.);skin=avatar.get('玩家皮肤','')
    env=dict(玩家血量=avatar['玩家血量']*20./maximum if maximum!=20. else avatar['玩家血量'],玩家受伤=avatar.get('玩家受伤',0),
             玩家恢复=avatar.get('玩家恢复',0),玩家倒地=avatar.get('玩家倒地',0),玩家皮肤=skin,图集={skin+'-受伤':_DaveImage()},int=int)
    exec(DAVE_STATE,env);avatar['玩家受伤']=env['玩家受伤']
class NativeTickExtension(zombies.ContentZombie64Extension,maintenance.MaintenanceExtension,
                          binding.GraveBindingExtension,utilities.PlantUtilitiesExtension,
                          paths_module.SeatPathExtension,heroes.HeroPhaseExtension,actions.ActionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;g=self.g;env=self.tick_ref=ref['native_tick']
        self.tick_seen=False;self.tick_events=[];b.profiler=None
        self.tick_mark_seconds=case.get('mark_seconds',8.)
        b._suspended_graves=[];b._sun_source_start=None
        b.graphics=types.SimpleNamespace(skip_dave_pixels=False)
        b.status=types.SimpleNamespace(tick=lambda:self.record('status'))
        b.recorder=types.SimpleNamespace(enabled=True,entity_override=None,
            begin_frame=lambda tick:self.record('begin_frame'),snapshot=lambda:self.record('snapshot'))
        b.engine.regions.update(env['regions'])
        b.engine.regions['plants']=self.plant_ref['region']
        b.engine.regions['plant_maintenance']=self.death_ref['region']
        b.engine.root=ref['world_rules']['root']
        b.engine.draw_plants=lambda:self.record('draw_plants')
        b.content.before_tick=lambda:self.record('content_before')
        b.content.finish_zombie=lambda:self.record('content_zombie_finish')
        b.content.projectiles=lambda:self.record('content_projectiles')
        b.content.after_plants=lambda:self.record('content_after')
        b.content.pvp64=self.taunt;b.content.wind=self.shoot_wind;b.content.sea=self.sea
        self.shoot_wind_content.pvp64=self.grenadiers
        b.content.barrels=types.SimpleNamespace(reconcile=lambda:self.record('barrels'),
            draw=lambda unit:self.record('barrel_'+str(self.label(unit))))
        b.expansion.finish_zombie=lambda:self.record('expansion_zombie_finish')
        b.expansion.before_plants=lambda:self.record('expansion_before')
        b.expansion.after_plants=lambda:self.record('expansion_after')
        def patch_before(now):
            self.native_time=now
            self.record('patch_before')
        b.patch.before_native_tick=patch_before
        b.patch.after_native_tick=lambda now:self.record('patch_after')
        b.patch.draw=lambda now:self.record('patch_draw')
        b._finish_sun_source=lambda:self.record('sun_source')
        b._card=lambda side,key:self.cards[key]
        b.gravebusters=self.bridge
        for name,method in env['Driver'].__dict__.items():
            if callable(method):setattr(b,name,types.MethodType(method,b))
        env['draw_dave']=lambda game,root,avatar,materialize:(self.record('hero_'+avatar['_pvp_seat']+('_pixels' if materialize else '_hidden')),dave_state_region(avatar))
        original=g['_pvp_zombie_gate']
        def gate():
            original();self.before('tick_zombie_gate');self.after('tick_zombie_gate')
        g['_pvp_zombie_gate']=gate
        # The original driver assigns recorder.enabled between begin_frame
        # and the native draw flag. Observe that exact assignment separately.
        parent=self
        class Recorder:
            entity_override=None
            def __init__(self):self._enabled=True
            def begin_frame(self,tick):parent.record('begin_frame')
            @property
            def enabled(self):return self._enabled
            @enabled.setter
            def enabled(self,value):parent.record('drawing' if value else 'hidden');self._enabled=value
            def snapshot(self):parent.record('snapshot')
        b.recorder=Recorder()

    def record(self,name):
        self.tick_events.append([name,self.b.engine.native_tick,self.g.get('_pvp_native_tick',0),self.native_time])
        self.before('tick_'+name);self.after('tick_'+name)

    def operation(self,op):
        name=op['op'];b=self.b;g=self.g
        if name=='native_tick_setup':
            self.tick_seen=True;b.present=frozenset(op['present']);b.native_secrets=list(op['native_secrets'])
            g['_pvp_native_tick']=b.engine.native_tick
            b._multi_target=op['multi_target'];b._multi_plant=op['multi_plant']
            b.scripted=op['scripted'];self.budget.enabled=b.scripted;b.team_mode=op['team_mode']
            b.graphics.skip_dave_pixels=op['skip_pixels'];b.command=op['command'];b.commands=dict(op['commands'])
            b.terrain_revision=0
            b.rules.update(mark_seconds=self.tick_mark_seconds,tail_activation_seconds=op['tail_at'],production_multiplier=op['multiplier'],
                producer_rest_seconds=op['quiet'],producer_rest_ramp_seconds=op['ramp'],
                producer_rest_bonus=op['bonus'],hero_lock_range=360.)
            for seat,avatar in b.hero_states.items():avatar['_pvp_seat']=seat
        elif name=='tick_grenade_wind':
            return self.ns[shooting.P+'apply_blover_zombie_wind'](g,self.units[op['unit']],op.get('strength',1.))
        elif name in ('tick_unit','tick_anchor_identity'):
            unit=self.units[op['unit']]
            if name=='tick_anchor_identity':unit['位置'][0]=op['x']
            else:unit.update(copy.deepcopy(op['fields']))
        elif name=='native_tick':
            try:b._step_original(op.get('draw',True))
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='native_zombie_phase':
            try:
                scope=dict(self.tick_ref,self=b,prof=None)
                exec(self.tick_ref['zombie_phase'],scope)
                return [self.label(unit) for unit in scope['graves']]
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.tick_seen:return
        b=self.b;source=b.recorder.entity_override
        if source is not None:
            source=source.get('_pvp_seat') if '_pvp_seat' in source and '玩家血量' in source else self.label(source)
        row['native_tick']=dict(tick=b.engine.native_tick,published=self.g.get('_pvp_native_tick',0),
            draw=not self.g.get('补帧',0),events=self.tick_events,
            suspended=[self.label(unit) for unit in b._suspended_graves],override=source,binding_depth=self.bridge._depth)


def paths():
    result=zombies.paths()
    result += [Path(module.__file__).resolve() for module in (maintenance,binding,utilities,paths_module,heroes,actions)]
    result += [Path(__file__).resolve(),shared.ROOT/'tools/typed72/native_tick_probe.cpp',shared.BATTLE]
    result += [shared.ROOT/('extract/live/'+name+'.marshal') for name in
               ('zombie_coordinates','zombie_body_index','particles','plants','plant_maintenance','zombies')]
    return result


def cases():
    result=[]
    prototype=actions.cases()[0][1]
    plant_setup=next(op for op in utilities.plants.cases()[0][1]['operations'] if op['op']=='plant_region_setup')
    hero_setup=next(op for op in heroes.cases()[1][1]['operations'] if op['op']=='hero_phase_setup')
    for i in range(16):
        case=copy.deepcopy(prototype);case['seed']=1100000+i
        ops=case['operations']=case['operations'][:5]
        mode=('duel','duo','pve','coop')[i%4]
        seats={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],
               'pve':['plant'],'coop':['plant','plant2']}[mode]
        ops[0]['mode']=mode
        for seat in case['players']:case['players'][seat]['secrets']=[]
        setup=copy.deepcopy(hero_setup);setup['seats']={seat:value for seat,value in setup['seats'].items() if seat in seats}
        for seat,value in setup['seats'].items():
            value.update(deck=[],native_secrets=[],move=0,held=False,presses=0)
        ops += [copy.deepcopy(plant_setup),dict(op='action_setup',draw=False),setup,
            dict(op='path_setup',point=[264.,412.8],targets=['向日葵','豌豆射手','坚果'],producers=['向日葵'],hold=0.,output=0.,running=1.),
            dict(op='native_tick_setup',present=seats,native_secrets=[],multi_target=mode in ('coop','duo'),
                 multi_plant=mode in ('coop','duo'),scripted=mode in ('coop','pve'),team_mode=mode in ('coop','duo'),
                 skip_pixels=i%2==0,tail_at=1000.,quiet=20.,ramp=20.,bonus=1.,multiplier=2.,command='follow',commands={})]
        for j in range(4):ops.append(dict(op='native_tick',draw=(i+j)%2==0))
        result.append(('native-tick-baseline-'+str(i),case))
    baselines=copy.deepcopy(result)
    def setup(index):
        case=copy.deepcopy(baselines[index%len(baselines)][1])
        case['seed']=1101000+index
        case['operations']=case['operations'][:-4]
        return case,case['operations']
    for i in range(32):
        case,ops=setup(i)
        for unit in (1,2,3):
            fields={'_pvp_grave':unit!=3,'_pvp_orphan_barrel':unit!=1,
                    '血量':(0.,40.,-1.,100.)[(i+unit)%4],'_pvp_id':'grave-'+str(unit),
                    '_pvp_owner':'zombie','位置':[240.+unit*48.,432.,0.,0.],
                    '_pvp_producer':True,'_pvp_idle':i,'_pvp_anchor':[280.+unit*48.,432.]}
            if unit==1 and i%2:fields['灰烬']=0.
            ops.append(dict(op='tick_unit',unit=unit,fields=fields))
        ops.append(dict(op='roster_replace',targets=[0,1,2,2,3]))
        ops.append(dict(op='native_zombie_phase'))
        result.append(('native-zombie-partition-'+str(i),case))
    for i in range(32):
        case,ops=setup(100+i)
        ops.append(dict(op='tick_unit',unit=1,fields={'_pvp_grave':True,'血量':100.,'_pvp_id':'held-grave'}))
        ops.append(dict(op='roster_replace',targets=[0,1]))
        name=('tick_zombie_gate','tick_content_zombie_finish','tick_expansion_zombie_finish','tick_content_zombie_finish')[i%4]
        hook=dict(op='lifecycle_hook',name=name)
        if i//4%2:hook['fail_after']=True
        else:hook['fail_before']=True
        if i//8%2:hook['body']=[dict(op='roster_replace',targets=[0,0])]
        ops += [hook,dict(op='native_zombie_phase',catch=True)]
        result.append(('native-zombie-cleanup-'+str(i),case))
    for i in range(32):
        case,ops=setup(200+i)
        for unit in (0,1):
            ops.append(dict(op='tick_unit',unit=unit,fields={'_pvp_grave':True,'血量':1000.,
                '_pvp_id':'target-'+str(unit),'_pvp_owner':'zombie','位置':[480.+unit*48.,432.,0.,0.]}))
        ops.append(dict(op='roster_replace',targets=[0,1]))
        for plant,kind in enumerate(('豌豆射手','向日葵','坚果')):
            ops += [dict(op='plant_original',name=kind,cell=[8,3+plant],facing=1.),
                dict(op='plant_fields',plant=plant,fields={'_pvp_owner':'plant','射':49. if plant==0 else 0.,
                    '射cd':-1.,'植物血':0. if plant==2 and i%3==0 else 100.},erase=['睡觉']),
                dict(op='producer_fields',plant=plant,fields={'_pvp_sun_due':(0.,1.,125.,126.)[i%4]})]
        ops.append(dict(op='producer_card',id='plant:向日葵',fields={'period':5.,'producer':True}))
        for j in range(16):ops.append(dict(op='native_tick',draw=j%4==3))
        result.append(('native-tick-plants-projectiles-'+str(i),case))
    for i in range(16):
        case,ops=setup(300+i)
        ops += [dict(op='tick_unit',unit=0,fields={'_pvp_grave':True,'血量':100.,'_pvp_id':'anchored',
                    '位置':[960.+i,432.,3.,4.],'_pvp_anchor':[-.5,420.]}),
                dict(op='tick_unit',unit=1,fields={'_pvp_orphan_barrel':True,'血量':100.,
                    '位置':[-.25,432.,0.,0.]}),dict(op='roster_replace',targets=[0,1]),
                dict(op='native_tick',draw=i%2==0),dict(op='native_tick',draw=i%2!=0)]
        result.append(('native-tick-frame-boundaries-'+str(i),case))
    for i in range(32):
        case,ops=setup(400+i)
        ops += [dict(op='roster_replace',targets=[0]),
                shooting.write(0,植物僵尸=True,植物僵尸名='三叶草僵尸',位置=[264.,432.,0.,0.],方向=(-1.,1.)[i%2]),
                dict(op='grenade_setup',height=576.,costs={},secrets={})]
        def shot(x,age=0,defused=False):
            return dict(op='grenade_add',fields=dict(x=x,y=365.,vx=.5,vy=-.25,owner='zombie',
                source='launched',target='missing',cell=[0,0],defused=defused,age=age))
        ops.append(shot((220.,300.,960.+240.,-500.)[i//2%4],898 if i%3==0 else 0,i%3==0))
        ops += [dict(op='tick_grenade_wind',unit=0,strength=(.25,1.,3.,-1.)[i//8]),dict(op='grenade_update'),
                dict(op='tick_grenade_wind',unit=0),dict(op='grenade_update'),
                shot(270.),dict(op='tick_grenade_wind',unit=0),dict(op='grenade_clear'),
                shot(255.),dict(op='tick_grenade_wind',unit=0)]
        result.append(('native-grenade-shared-wind-roster-'+str(i),case))
    return result


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,NativeTickExtension,'typed72-native-driver-composition'))
