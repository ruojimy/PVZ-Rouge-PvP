"""Literal NativeContent gate/finish composed with clocks, queries, PvP64 and summons.

The September, PvP56, PvP70 and barrel boundaries are explicit observations.
This verifier cannot establish completion of those controllers or a product.
"""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_content_status_reference',HERE/'verify_native_status.py')
status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)
driver=status.driver
shared=driver.shared;shooting=driver.shooting;hero=driver.hero
SOURCE=shared.LOCAL/'native_content.py'
CART=shared.PVP/'cart_lifecycle.py'
CROW=shared.PVP/'pvp61_content.py'
CATALOG=shared.PVP/'content_catalog.py'
CROW_CATALOG=shared.PVP/'pvp61_catalog.py'
FIELDS=('_pvp_ai_player_position','_pvp_saved_basketball_cd','_pvp_summon_clock','_pvp_cannon_rate',
        '_pvp_cart_deadline','_pvp_cannon_anim','_pvp_cannon_recoil','_pvp_cart_expired','_pvp_cannon_loaded',
        '_pvp_barrel_direction','_pvp_barrel_remaining','_pvp_barrel_broken','_pvp_barrel_discarded',
        '_pvp_barrel_detached','_pvp_target','_pvp_blown','_pvp_hop_clock','_pvp_walk_speed','_pvp_zs_locked',
        '_pvp_content_position_before','坚持分兵','再出场','出场','炸音','中场','跳舞cd','灯光','前进',
        '篮球cd','篮球总量','投篮','撞车','轮子','雪容量','丢小鬼','苏醒','红眼','半血','憋气','跳跃cd','啃咬','移速','篮球')


def reference():
    ref=status.reference();env=dict(math=math,__package__=shared.PACKAGE)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    for key in ('SCARECROW','CROW'):env[key]=hero.constant(CROW_CATALOG,key)
    env['CAPTAIN']=hero.constant(SOURCE,'CAPTAIN')
    env['FLYERS']=('海盗鹦鹉',env['CROW']);env['PVP61_ZOMBIES']=(env['SCARECROW'],env['CROW'])
    env['ZOMBIES']=hero.constant(CATALOG,'ZOMBIES')
    hero.selected_class(SOURCE,['zombie_gate','release_pending_destination','finish_zombie','flyer_bite_effect','summon'],
                        'Controller',env)
    cart=dict(math=math)
    for node in ast.parse(CART.read_text(encoding='utf8')).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in
                ('CART_LIFETIME_TICKS','CARTS','CANNON_PERIOD','CANNON_LOAD_TICKS') for t in node.targets):
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(CART),'exec'),cart)
    shooting.projectiles.functions(CART,['action_rate'],cart)
    hero.selected_class(CART,['configure','before_zombie','animate'],'Carts',cart)
    crow=dict(env)
    for key in ('LIGHTNING_REED','OVERLOAD_REED','CROW_DAMAGE'):crow[key]=hero.constant(CROW_CATALOG,key)
    for path,key in ((CROW_CATALOG,'REEDS'),(CROW,'ZOMBIES')):
        node,=[n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id==key for t in n.targets)]
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),crow)
    crow['HOP_PERIOD']=hero.constant(CROW,'HOP_PERIOD')
    hero.selected_class(CROW,['configure','grave_goal','scarecrow_step'],'Crows',crow)
    ref.update(content_zombies=env,content_carts=cart,content_crows=crow)
    return ref


class ContentZombiesExtension(status.NativeStatusExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;g=self.g;r=self.controller=self.content
        for key,method in ref['content_zombies']['Controller'].__dict__.items():
            if callable(method):setattr(r,key,types.MethodType(method,r))
        r.last_zombie=None;r.b=b;r.g=g
        self.content_seen=False;self.content_events=[];self.cart_events=[];self.summon_events=[];self.installed=False
        self.movement=1.;self.bite=1.;self.content_heights={}
        scale_env=dict(FACTOR=copy.deepcopy(case['world_rules'].get('scale',{})))
        shooting.projectiles.functions(shooting.projectiles.SCALE,['factor'],scale_env)
        sys.modules[shared.PACKAGE+'.native_scale'].factor=scale_env['factor']
        self.carts=ref['content_carts']['Carts']();self.carts.b=b
        r.carts=types.SimpleNamespace(before_zombie=lambda unit:self.cart_before(unit),
            animate=lambda unit,active,fired:self.cart_animate(unit,active,fired))
        september=r.september
        september.zombie_gate=lambda unit:self.event('september_gate',unit)
        september.wave_chase=lambda unit:self.event('wave_chase',unit)
        september.finish_zombie=lambda unit:self.event('september_finish',unit)
        r.zombies56=types.SimpleNamespace(zombie_gate=lambda unit:self.event('zombies56_gate',unit),
            finish_zombie=lambda unit:self.event('zombies56_finish',unit))
        r.pvp70.zombie_gate=lambda unit:self.event('zombies70_gate',unit)
        # Concrete query helpers and the existing PvP64 gate share one taunt object.
        for key,method in ref['content_queries']['Queries'].__dict__.items():
            if callable(method):setattr(r,key,types.MethodType(method,r))
        r.pvp64=self.zombies64;r.pvp64.taunt_target=self.taunt.taunt_target
        r.pvp64.restore_taunt=self.taunt.restore_taunt;r.pvp64.update_taunts=self.taunt.update_taunts
        r.pvp61=ref['content_crows']['Crows']();r.pvp61.b=b;r.pvp61.g=g;r.pvp61.c=r
        r.barrels.correct_pair=lambda unit:self.event('barrel_correct',unit)
        r.barrels.detach=lambda unit,remaining=0:self.event('barrel_detach',unit,remaining)
        r.barrels.contact_plants=lambda unit,factor:self.event('barrel_contact',unit,factor)
        r.break_barrel=lambda unit:self.event('barrel_break',unit)
        r.move_barrel=lambda unit,factor:self.event('barrel_move',unit,factor)
        r.draw_zombie=lambda unit:self.event('draw',unit)
        def bite(unit,target):self.event('bite',unit,self.content_label(target));return self.bite
        r.bite_damage=bite
        b.zsecrets.movement_factor=lambda unit:self.movement
        b.status.tint_zombie=lambda unit:self.event('tint',unit)
        emit=b._emit
        def event(name,**fields):
            if name=='cart_expired':
                self.cart_events.append([name,fields]);self.before('cart_expired');self.after('cart_expired')
            elif name=='content_summon':
                self.summon_events.append([name,fields]);self.before('content_summon_event');self.after('content_summon_event')
            else:emit(name,**fields)
        b._emit=event
        lower_gate=g['_pvp_zombie_gate']
        def gate():
            if self.installed:r.finish_zombie()
            lower_gate()
            if self.installed:r.zombie_gate()
        g['_pvp_zombie_gate']=gate
        finish=r.finish_zombie;release=r.release_pending_destination
        # Expose unwrapped methods for direct gate/finish tests, while the main
        # driver still records its explicit controller boundary first.
        self.finish=finish;self.release=release
        def driver_finish():
            self.record('content_zombie_finish')
            if self.installed:finish()
        def driver_release():
            self.render_log.append(['release_destination'])
            if self.installed:release()
        b.content.finish_zombie=driver_finish;b.content.release_pending_destination=driver_release
        # gate() must close the original finish, not the observed driver wrapper.
        def gate():
            if self.installed:finish()
            lower_gate()
            if self.installed:r.zombie_gate()
        g['_pvp_zombie_gate']=gate
        # The raw-region fixture omits pygame when no presentation boundary
        # needs it. Supply only the transform observed by these literal stars.
        if 'pygame' not in g:g['pygame']=types.SimpleNamespace(transform=types.SimpleNamespace(scale=lambda image,size:image))
        original_scale=g['pygame'].transform.scale;original_draw=g.get('摄像显示',lambda image,point:None)
        class Star:
            def __init__(self,size=None):self.size=size
        self.Star=Star;g['图集']['星星']=Star()
        def scale(image,size):
            return Star(size) if isinstance(image,Star) else original_scale(image,size)
        def draw(image,point):
            if isinstance(image,Star):
                self.content_events.append(['star',list(point),list(image.size)])
                self.before('content_star');self.after('content_star')
            else:return original_draw(image,point)
        g['pygame'].transform.scale=scale;g['摄像显示']=draw

    def event(self,name,unit,*extra):
        self.content_events.append([name,self.label(unit)]+list(extra))
        self.before('content_'+name);self.after('content_'+name)

    def cart_before(self,unit):
        self.event('cart_before',unit);self.carts.before_zombie(unit)

    def cart_animate(self,unit,active,fired):
        self.event('cart_animate',unit,active,fired);self.carts.animate(unit,active,fired)

    def operation(self,op):
        name=op['op'];b=self.b;g=self.g;r=self.controller
        if name=='content_zombies_setup':
            b.map['rows']=len(g['ditu']);b.map['cols']=len(g['ditu'][0])
            self.content_seen=True;self.installed=op.get('installed',False)
            self.movement=op.get('movement',1.);self.bite=op.get('bite',1.);self.content_heights=dict(op['heights'])
            for key,height in self.content_heights.items():
                g['图集'][key]=types.SimpleNamespace(get_height=lambda height=height:height)
        elif name=='content_zombie_fields':
            unit=self.units[op['unit']];unit.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):unit.pop(key,None)
        elif name=='content_borrow':
            unit=self.units[op['unit']];unit.setdefault('_pvp_ai_player_position',g['玩家位置'])
            g['玩家位置']=list(op['position'])
        elif name=='content_player_write':g['玩家位置'][0]=op['x']
        elif name=='content_orders':b.command=op['command'];b.commands.update(op['commands'])
        elif name=='content_flag':b.set_rally(op['side'],dict(x=op['point'][0],y=op['point'][1]) if op['point'] is not None else None)
        elif name=='content_drawing':g['补帧']=not op['draw']
        elif name=='content_scarecrow':return r.pvp61.configure(self.units[op['unit']],dict(content=op['name'],hp=op['hp']))
        elif name in ('content_gate','content_finish','content_release','content_cart_configure','content_cart_before','content_cart_animate'):
            try:
                unit=self.units[op['unit']] if 'unit' in op else None
                if name=='content_gate':
                    g['l']=next(i for i,z in enumerate(g['僵尸']) if z is unit);r.zombie_gate()
                elif name=='content_finish':self.finish()
                elif name=='content_release':self.release()
                elif name=='content_cart_configure':self.carts.configure(unit,dict(id=op['card']))
                elif name=='content_cart_before':self.carts.before_zombie(unit)
                else:self.carts.animate(unit,op['active'],op['fired'])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.content_seen:return
        seen={}
        def identity(value):
            if value is None:return None
            if id(value) not in seen:seen[id(value)]=len(seen)
            return seen[id(value)]
        identities=[identity(self.g.get('玩家位置'))]
        for seat in ('plant','zombie','plant2','zombie2'):
            if seat in self.b.hero_states:identities.append([seat,identity(self.b.hero_states[seat].get('玩家位置'))])
        records=[]
        for unit in self.units:
            item={key:unit[key] for key in FIELDS if key in unit};item['_pvp_zs_lock_done']=unit.get('_pvp_zs_lock_done',False)
            records.append(item);identities.append(identity(unit.get('_pvp_ai_player_position')))
        row['content_zombies']=dict(last=self.label(self.controller.last_zombie) if self.controller.last_zombie is not None else None,
            events=self.content_events,summons=self.summon_events,carts=self.cart_events,units=records,identities=identities)


def paths():
    paths=[]
    for path in status.paths():
        if path.name in ('native_tick_probe.cpp','native_status_probe.cpp'):path=HERE/path.name
        paths.append(path)
    return (paths+[Path(__file__).resolve(),HERE/'content_zombies_probe.cpp',SOURCE,CART,CROW,CATALOG,CROW_CATALOG]+
        [HERE/name for name in ('content_zombies.h','content_zombies.cpp','content_zombie_state.h','cart_lifecycle.h','cart_lifecycle.cpp')])


def cases():
    baselines=driver.cases()[:16];result=[]
    custom=hero.constant(CATALOG,'ZOMBIES')
    heights={name+'-帧0':height for name,height in (('海盗鹦鹉',60.),('乌鸦',36.),('稻草人',80.),('滚桶僵尸',90.),('抓人草触手',70.))}
    def setup(i):
        # Native helpers initialize all four hero aliases for duel/duo.
        case=copy.deepcopy(baselines[(i%2)][1]);case['seed']=1240000+i
        ops=case['operations']=case['operations'][:-4]
        ops += [dict(op='zombie64_setup',mode=('duel','duo')[i%2],secrets={}),dict(op='poison_setup'),
                dict(op='content_zombies_setup',custom=list(custom),heights=heights),
                dict(op='content_orders',command='attack',commands={}),dict(op='content_drawing',draw=False),
                dict(op='flying_published',solid=[[0]*20 for unused in case['plant_world']['grid']])]
        for unit in range(4):
            ops.append(dict(op='content_zombie_fields',unit=unit,fields={'血量':100.,'位置':[264.+unit*120.,432.,0.,0.],
                '_pvp_owner':'zombie','_pvp_seat':'zombie','_pvp_id':'body-'+str(unit),'_pvp_content':'',
                '大小':2.,'黄油':0.,'冰冻':0.,'眩晕':0.,'啃咬':0.,'_pvp_no_attack':False},erase=['魅惑','灰烬']))
        ops.append(dict(op='roster_replace',targets=[0]))
        return case,ops
    def fields(ops,**value):ops.append(dict(op='content_zombie_fields',unit=0,fields=value))
    def cycle(ops):ops.extend([dict(op='content_gate',unit=0),dict(op='content_finish'),dict(op='content_finish')])
    for i in range(32):
        case,ops=setup(i)
        name=('','海盗船长','滚桶僵尸','小鬼炮')[i%4]
        fields(ops,_pvp_content=name,_pvp_summon_clock=0.,_pvp_barrel_direction=-1.,手持='滚桶',手持血量=30.,
               **{'僵尸':'投篮车僵尸' if name=='小鬼炮' else '普通僵尸','血量':(100.,0.)[i//4%2],
                  '位置':[264.,432.,(-2.,0.,2.,.01)[i//8],0.]})
        if i%8==6:fields(ops,灰烬=0.)
        ops.append(dict(op='poison_clock',tick=(34,35,69,70)[i//8]));cycle(ops)
        result.append(('content-gate-order-death-alias-and-capture-'+str(i),case))
    for i in range(32):
        case,ops=setup(100+i)
        fields(ops,僵尸='投篮车僵尸',_pvp_card=('zombie:投篮车僵尸',None,'other','zombie:投篮车僵尸')[i%4],
               篮球=(0.,4.)[i//4%2],篮球cd=(0.,1.,40.,100.)[i//8],_pvp_content='')
        ops.append(dict(op='content_orders',command='follow' if i%3 else 'attack',commands={'zombie':'follow'}))
        if i%4==3:ops.append(dict(op='content_flag',side='zombie',point=[850.,400.]))
        if i%5==0:fields(ops,魅惑=250.)
        if i%7==0:ops.append(dict(op='content_borrow',unit=0,position=[730.,220.,0.,0.]))
        ops += [dict(op='content_gate',unit=0),dict(op='content_player_write',x=123.),dict(op='content_release'),dict(op='content_finish')]
        result.append(('content-cart-orders-borrowed-reference-and-cooldown-'+str(i),case))
    for i in range(48):
        case,ops=setup(200+i)
        fields(ops,_pvp_content=('海盗鹦鹉','乌鸦')[i%2],位置=[264.,432.,7.,8.],受伤=(0.,1.)[i//2%2],
               _pvp_blown=i//4%2==0,冰冻=(0.,1.,1001.)[i//8%3],_pvp_no_hero_attack=False)
        if i%4==0:fields(ops,魅惑=(199.,200.,999.)[i//8%3])
        if i%6==1:ops.append(dict(op='content_orders',command='follow',commands={'zombie':'follow'}))
        if i%6==2:ops.append(dict(op='content_flag',side='zombie',point=[850.,385.]))
        ops += [dict(op='content_gate',unit=0),dict(op='content_zombie_fields',unit=0,fields={'位置':[450.,500.,-4.,-5.]}),dict(op='content_finish')]
        result.append(('content-flyers-charm-follow-rally-freeze-and-impulse-'+str(i),case))
    for i in range(32):
        case,ops=setup(300+i)
        name=('海盗船长','小鬼炮')[i%2]
        fields(ops,_pvp_content=name,_pvp_summon_clock=(999.,1000.,1999.,2000.)[i//2%4],
               僵尸='投篮车僵尸' if name=='小鬼炮' else '普通僵尸',冰冻=(0.,1.,1001.,0.)[i//8])
        if i%5==0:ops.append(dict(op='content_orders',command='follow',commands={'zombie':'follow'}))
        if i%5==1:ops.append(dict(op='content_flag',side='zombie',point=[850.,400.]))
        ops.append(dict(op='zombie64_spawn_mode',value=('ok','none','ok','ok')[i//8]))
        cycle(ops);result.append(('content-summoner-admission-and-cannon-clocks-'+str(i),case))
    for i in range(32):
        case,ops=setup(400+i)
        card=('zombie:小鬼炮','zombie:投篮车僵尸')[i%2]
        fields(ops,僵尸='投篮车僵尸',_pvp_content='小鬼炮' if i%2==0 else '',_pvp_card=card,
               _pvp_summon_clock=(799.,800.,1000.,1200.)[i//2%4],_pvp_zs_locked=True,篮球=10.,篮球总量=100.,投篮=45.)
        ops += [dict(op='poison_clock',tick=0),dict(op='content_cart_configure',unit=0,card=card),
                dict(op='poison_clock',tick=(19999,20000,20001,50000)[i//8])]
        fields(ops,冰冻=(0.,1.,1001.,0.)[i//4%4],黄油=1. if i%7==0 else 0.)
        cycle(ops);ops.append(dict(op='content_cart_before',unit=0))
        result.append(('content-cart-lifetime-independent-of-orders-and-status-'+str(i),case))
    for i in range(16):
        case,ops=setup(500+i)
        ops.append(dict(op='content_scarecrow',unit=0,name='稻草人',hp=100.))
        fields(ops,_pvp_hop_clock=229.,眩晕=(0.,1.)[i%2],冰冻=(0.,1.,1001.,0.)[i//2%4])
        ops += [dict(op='content_zombie_fields',unit=1,fields={'_pvp_grave':True,'_pvp_owner':'zombie'}),
                dict(op='roster_replace',targets=[0,1]),dict(op='content_drawing',draw=True)]
        cycle(ops);result.append(('content-scarecrow-motion-and-stun-stars-'+str(i),case))
    for i in range(20):
        case,ops=setup(600+i)
        poison=(None,{},dict(level=1),dict(level=2),dict(layers=None))[i%5]
        ops.append(dict(op='poison_fields',unit=0,state=poison));cycle(ops)
        result.append(('content-poison-dictionary-truthiness-'+str(i),case))
    for i in range(24):
        case,ops=setup(700+i)
        fields(ops,僵尸='投篮车僵尸',_pvp_card='zombie:投篮车僵尸',篮球=2.,篮球cd=25.)
        ops.append(dict(op='content_orders',command='follow',commands={'zombie':'follow'}))
        hook=('cart_before','september_gate','zombies56_gate','wave_chase','zombies70_gate','september_finish','zombies56_finish','draw')[i%8]
        ops.append(dict(op='lifecycle_hook',name='content_'+hook,fail_before=i//8==0,fail_after=i//8==1,
                        body=[dict(op='content_zombie_fields',unit=0,fields={'血量':0.})] if i//8==2 else []))
        ops.extend([dict(op='content_gate',unit=0,catch=True),dict(op='content_release',catch=True),
                    dict(op='content_finish',catch=True),dict(op='content_finish',catch=True)])
        result.append(('content-gate-finish-exception-retention-'+str(i),case))
    return result


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,ContentZombiesExtension,'typed72-content-zombies',probe_timeout=600))
