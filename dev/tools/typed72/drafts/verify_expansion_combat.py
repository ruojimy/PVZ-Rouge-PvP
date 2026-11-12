"""Literal NativeExpansion constructor and combat methods on the native chain.

Armor seating/pixel compositing and barrel correction are explicitly observed
service boundaries. These cases do not certify the finished renderer/product.
"""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import types
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('expansion_garden_reference',HERE/'verify_expansion_garden.py')
garden=importlib.util.module_from_spec(spec);spec.loader.exec_module(garden)
shared=garden.shared;shooting=garden.shooting;hero=garden.hero
SOURCE=garden.SOURCE;CATALOG=shared.PVP/'expansion_catalog.py'
STATE=('_pvp_black_armor','_pvp_before_vy','_pvp_charge_until','_pvp_charge_ready','_pvp_charge_cd','_pvp_charging',
       '_pvp_paralysis_until','_pvp_paralysis_started','_pvp_paralysis_garlic')
UNIT=STATE+('_pvp_variant','_pvp_base_speed','_pvp_poison_killed','_pvp_armor_triggered','_pvp_imp_armor','_pvp_imp_armor_hp',
            '大蒜','移速','出场','眩晕','撑杆')

def reference():
    ref=garden.reference();env=dict(math=math)
    tree=ast.parse(CATALOG.read_text(encoding='utf8'))
    constants=('PARALYSIS_FREEZE_SECONDS','PARALYSIS_FREEZE_TICKS','BLACK_ZOMBIES','GLADIATOR_ZOMBIES')
    assignments=[node for node in tree.body if isinstance(node,ast.Assign) and
                 any(isinstance(target,ast.Name) and target.id in constants for target in node.targets)]
    assert len(assignments)==len(constants)
    exec(compile(ast.Module(body=assignments,type_ignores=[]),str(CATALOG),'exec'),env)
    shooting.projectiles.functions(CATALOG,['variant_setup'],env)
    for key in ('IMP_ARMOR','IMP_ARMOR_HP','IMP_BLACK_ARMOR','BLACK_ARMOR_DROP','BLACK_ARMOR_DAMAGE','BLACK_ARMOR_RADIUS','BLACK_BUCKET_RADIUS'):
        env[key]=hero.constant(SOURCE,key)
    shooting.projectiles.functions(SOURCE,['black_armor_radius','worn_black_armor','art_key','atlas_name'],env)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    hero.selected_class(SOURCE,['__init__','configure','armor_drop','black_armor_blast','finish_zombie','zombie_gate',
        'restore_art','alias_art','source_gate','_aim_pea','apply_paralysis','paralysis_recovery','charge','seated_headgear'],'CombatExpansion',env)
    hero.selected_class(shooting.projectiles.SIMULATION,['cell'],'CellBattle',env)
    hero.selected_class(hero.ZSECRETS,['blast_scale'],'BlastSecret',env)
    ref['expansion_combat']=env
    return ref

class ExpansionExtension(garden.GardenExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.expansion_seen=False;self.expansion_installed=False;self.expansion_events=[];self.expansion_atlas={};self.expansion_barrels=set()
        b=self.b;g=self.g;env=ref['expansion_combat'];self.expansion_ref=env
        g.setdefault('显示植物',lambda *args,**kwargs:None)
        r=self.expansion=env['CombatExpansion'](b)
        self.raw_damage=g['伤害僵尸']
        # Preserve original ctor closure; the typed wrapper is installed at the
        # same outer damage boundary. No arithmetic is reimplemented here.
        self.expansion_damage=g['伤害僵尸']
        r.armor_clear=lambda:self.expansion_events.append(['clear'])
        r.armor_gate=lambda unit:self.expansion_events.append(['armor',self.label(unit)])
        g['旋转摄像显示']=lambda image,point,angle,*args:self.expansion_events.append(['pole',*point])
        b.content.barrel_active=lambda unit:id(unit) in self.expansion_barrels
        b.content.barrels.correct_pair=lambda unit:self.expansion_events.append(['barrel',self.label(unit)])
        b.zsecrets.blast_scale=types.MethodType(env['BlastSecret'].blast_scale,b.zsecrets)
        b.cell=types.MethodType(env['CellBattle'].cell,b)
        # This composition uses the actual native omitted-target collector,
        # replacing DoomExtension's deliberately fixed extras-only fixture.
        b._native_objects={}
        g['_pvp_target_extras']=eval(ref['native_provider'],dict(self=b))
        emit=b._emit
        def event(name,**fields):
            if name=='black_armor_drop':self.expansion_events.append(['black',fields['variant'],fields['x'],fields['y']])
            else:emit(name,**fields)
        b._emit=event
        previous=b.expansion.finish_zombie
        def finish():
            previous()
            if self.expansion_installed:r.finish_zombie()
        b.expansion.finish_zombie=finish
        original_gate=g['_pvp_zombie_gate']
        def gate():
            original_gate()
            if self.expansion_installed:r.zombie_gate()
        g['_pvp_zombie_gate']=gate

    def operation(self,op):
        name=op['op'];b=self.b;g=self.g;r=self.expansion
        if name=='expansion_setup':
            self.expansion_seen=True;self.expansion_installed=op.get('installed',True)
            for seat,player in b.players.items():player['secrets']=list(op.get('secrets',{}).get(seat,[]))
            b.team_secrets={'plant':set(s for seat in b.team_seats('plant') for s in b.players[seat]['secrets'])}
            p=b.zsecrets;p.by_seat={seat:set(s.split(':',1)[-1] for s in b.players[seat]['secrets']) for seat in b.team_seats('zombie')}
            p.team=set().union(*p.by_seat.values()) if p.by_seat else set();p.enabled=bool(p.team)
            self.expansion_atlas={key:key for key in op.get('atlas',[])}
            g['图集'].update(self.expansion_atlas)
        elif name=='expansion_fields':
            target=self.target(op['target']);target.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):target.pop(key,None)
            if op.get('barrel'):self.expansion_barrels.add(id(target))
        elif name=='expansion_configure':
            expected=self.expansion_ref['variant_setup'](op['variant'])
            assert list(expected)==op['setup']
            r.configure(self.units[op['unit']],dict(expansion=op['variant']))
        elif name=='expansion_call':
            action=op['action']
            if action=='finish':r.finish_zombie()
            elif action=='restore':r.restore_art()
            elif action=='source':r.source_gate(self.all_plants[op['plant']] if 'plant' in op else self.births[op['entity']] if 'entity' in op else None)
            elif action=='hit':return self.expansion_damage(op['index'],op.get('facing',1.),op['amount'])
            else:
                target=self.target(op['target'])
                if action=='paralysis':r.apply_paralysis(target)
                elif action=='recovery':r.paralysis_recovery(target)
                elif action=='charge':r.charge(target)
                elif action=='gate':g['l']=next(i for i,u in enumerate(g['僵尸']) if u is target);r.zombie_gate()
                elif action=='drop':r.armor_drop(target)
                elif action=='blast':r.black_armor_blast(target,op['variant'])
                elif action=='worn':return self.expansion_ref['worn_black_armor'](target)
                else:raise ValueError(action)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.expansion_seen:return
        r=self.expansion
        row['expansion']=dict(units=[{key:u[key] for key in UNIT if key in u} for u in self.units],
            heroes={seat:{key:u[key] for key in STATE+('大蒜',) if key in u} for seat,u in self.c.proxies.items()},
            events=self.expansion_events,atlas={key:self.g['图集'][key] for key in self.expansion_atlas if self.g['图集'][key]!=key},
            last=self.label(r.last_zombie) if r.last_zombie is not None else None)

def cases():
    prototypes=garden.bonus.driver.cases();out=[]
    catalog={};tree=ast.parse(CATALOG.read_text(encoding='utf8'))
    nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('BLACK_ZOMBIES','GLADIATOR_ZOMBIES') for t in n.targets)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(CATALOG),'exec'),catalog)
    shooting.projectiles.functions(CATALOG,['variant_setup'],catalog)
    def setup(i,duo=False,secrets=None):
        c=copy.deepcopy(prototypes[1 if duo else 0][1]);c['seed']=1500000+i
        ops=c['operations']=c['operations'][:-4]
        ops += [dict(op='roster_replace',targets=[0,1,2,3]),dict(op='expansion_setup',secrets=secrets or {})]
        return c,ops
    def field(target,**values):return dict(op='expansion_fields',target=target,fields=values)
    def call(action,**values):return dict(op='expansion_call',action=action,**values)
    def unit(ops,i,owner='zombie',point=(264.,432.,0.,0.)):
        ops += [dict(op='plant_unit',unit=i,fields={'_pvp_owner':owner,'位置':list(point),'血量':200.},erase=['魅惑']),
                field(i,**{'移速':.16,'_pvp_base_speed':.16,'出场':500.,'眩晕':0.})]
    def plant(ops,name='豌豆射手',col=5,hp=12.,owner='plant'):
        index=sum(o['op']=='plant_original' for o in ops)
        ops += [dict(op='plant_original',name=name,cell=[8,col]),dict(op='plant_fields',plant=index,fields={'_pvp_owner':owner,'植物血':hp},erase=['睡觉'])]
        return index
    for i,(variant,_) in enumerate(list(catalog['BLACK_ZOMBIES'].items())+list(catalog['GLADIATOR_ZOMBIES'].items())):
        c,ops=setup(i);unit(ops,0)
        ops += [dict(op='expansion_configure',unit=0,variant=variant,setup=list(catalog['variant_setup'](variant))),call('worn',target=0)]
        out.append(('expansion-catalog-configure-'+variant,c))
    for i in range(48):
        c,ops=setup(20+i,duo=i%4==0,secrets={'zombie':['zsecret:沉默']} if i%6==5 else {})
        variant=('黑路障僵尸','黑铁桶僵尸')[i%2];owner=('plant','zombie')[i//2%2]
        for j in range(4):unit(ops,j,owner if j in (0,2) else ('zombie' if owner=='plant' else 'plant'),
            ((264.,384.,384.001,800.)[j],432.,0.,0.))
        for j in range(3):plant(ops,'咖啡豆' if j==2 else '豌豆射手',5+j,hp=(5.,6.,7.)[j],owner='plant' if j!=1 else 'zombie')
        ops += [dict(op='garden_avatar',seat='plant',hp=40.,point=[280.,432.]),dict(op='garden_avatar',seat='zombie',hp=40.,point=[300.,432.])]
        fields={'_pvp_variant':variant,'防具':'路障' if i%2==0 else '铁桶','防具血量':1.}
        if i%8==2:fields['_pvp_black_armor']=None
        if i%8==3:fields['_pvp_black_armor']=''
        if i%8==4:fields['_pvp_poison_killed']=True
        if i%8==5:fields['_pvp_armor_triggered']=True
        if i%8==6:fields.update(_pvp_variant='',_pvp_black_armor=variant)
        ops += [field(0,**fields),call('worn',target=0),call('drop',target=0),call('drop',target=0)]
        out.append(('expansion-black-drop-team-range-guard-'+str(i),c))
    for i in range(24):
        c,ops=setup(90+i);unit(ops,0);target=('plant','zombie',0)[i%3]
        ops += [dict(op='garden_tick',tick=100),field(target,**{'眩晕':(0.,63.,64.,1500.)[i//6],'大蒜':(0.,50.,200.)[i%3]}),call('paralysis',target=target)]
        if i//6<2:
            ops += [dict(op='garden_tick',tick=110),call('paralysis',target=target),field(target,**{'眩晕':(0.,60.,200.)[i%3],'大蒜':100.}),
                    dict(op='garden_tick',tick=120),call('recovery',target=target)]
        out.append(('expansion-paralysis-native-hero-and-external-stun-'+str(i),c))
    for i in range(28):
        c,ops=setup(130+i)
        for j in range(4):unit(ops,j,owner='plant' if j==3 else 'zombie',point=[(950.,10.,40.,15.)[j],432.,0.,0.])
        if i%7==1:plant(ops,col=0)
        if i%7==2:ops.append(field(0,**{'眩晕':1.}))
        if i%7==3:ops.append(field(0,**{'冰冻':1001.}))
        if i%7==4:ops.append(field(0,**{'黄油':1.}))
        if i%7==5:ops.append(field(0,**{'出场':499.}))
        ops += [dict(op='expansion_fields',target=1,fields={'_pvp_orphan_barrel':i%2==0},barrel=True),
                call('charge',target=0),dict(op='garden_tick',tick=1499),call('charge',target=0),
                field(0,**{'眩晕':1.}),call('charge',target=0),field(0,**{'眩晕':0.}),
                dict(op='garden_tick',tick=3000),call('charge',target=0)]
        out.append(('expansion-charge-clock-wrapped-allies-and-obstacles-'+str(i),c))
    for i in range(16):
        c,ops=setup(180+i);unit(ops,0)
        variant=('黑旗帜僵尸','黑普通僵尸','黑撑杆僵尸','黑橄榄僵尸')[i%4]
        native=catalog['variant_setup'](variant)[0]
        atlas=[root+suffix for root in ('路障','黑路障',native+'-身',native+'-首',variant+'-身',variant+'-首',variant+'-冲锋',variant+'-冲锋-首')
               for suffix in ('','-受伤','-冰冻','-灰烬','-魅惑')]+['撑杆']
        ops += [dict(op='expansion_setup',atlas=atlas),field(0,**{'_pvp_variant':variant,'僵尸':native,'防具':'路障','防具血量':3.,
                '血量':-.25 if i%4<2 else 100.,'撑杆':200.,'受伤':0.}),call('gate',target=0),
                dict(op='expansion_fields',target=0,fields={'位置':[264.,432.,0.,-1. if i//4%2 else 0.]},erase=['撑杆']),call('finish')]
        out.append(('expansion-gate-jump-rearm-alias-and-death-stall-'+str(i),c))
    for i in range(12):
        c,ops=setup(210+i,secrets={'plant':['secret:麻痹']})
        for j in range(4):unit(ops,j,owner='zombie' if j<3 else 'plant',point=[264.+j*25.,432.,0.,0.])
        target='zombie' if i%3==0 else 0
        if isinstance(target,str):ops.append(dict(op='roster_append',target=target))
        ops.append(field(0,**{'_pvp_variant':'黑路障僵尸','防具':'路障','防具血量':1.}))
        source=len(c['sources']);c['sources'].append({'植物':'地刺王','_pvp_owner':'plant'})
        ops += [dict(op='context',target='zombie',owner='plant',phase='plants',source=source,
            body=[call('hit',index=4 if isinstance(target,str) else 0,amount=(0.,1.,20.,200.)[i//3])])]
        out.append(('expansion-installed-damage-break-and-spikerock-'+str(i),c))
    return out

def paths():
    return garden.paths()+[Path(__file__).resolve(),SOURCE,CATALOG,shared.ROOT/'tools/typed72/expansion_combat_probe.cpp']

if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,ExpansionExtension,'typed72-native-expansion-combat',probe_timeout=600))
