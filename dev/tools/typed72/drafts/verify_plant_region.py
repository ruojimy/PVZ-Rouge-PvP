"""Installed native plant wordcode and exact predicate chain, with observed per-plant scheduling gate."""
import ast
import copy
import marshal
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_resources as res
shared=res.shared
shooting=res.shooting
hero=res.hero
RAW=shared.ROOT/'extract/live/plants.marshal'
FLYING=shared.PVP/'pvp56_plants.py'
FLYING_CATALOG=shared.PVP/'pvp56_plants_catalog.py'
SECRETS=shared.LOCAL/'pvp66_secrets.py'
CONTENT=shared.LOCAL/'native_content.py'
CONTENT70=shared.LOCAL/'pvp70_content.py'
CATALOG70=shared.PVP/'pvp70_catalog.py'
PERIODIC=res.phase.PERIODIC
UNIT_FIELDS=('出土','离开','出场','大小','冰冻','黄油','眩晕','出场初位置','出场末位置')


def reference():
    ref=res.reference()
    env=dict(math=math,__pvz_sb_math=math)
    constants,_=shooting.patch.patch_reference();env.update(constants)
    shooting.projectiles.functions(shooting.patch.PATCH,[shooting.P+n for n in ('float','sign','len2','star_angles','star_vector','starfruit_target')],env)
    flying=hero.constant(FLYING_CATALOG,'PLANTS');env.update(FLYING_PLANTS=flying,AIR_PLANTS=('幽灵辣椒',)+flying)
    for name in ('BASIN','HEAD'):env[name]=hero.constant(CATALOG70,name)
    # Reuse the actual shell catalog/functions loaded by the earlier oracle.
    env['PLANT_VINES']=ref['world_rules']['PLANT_VINES']
    shooting.projectiles.functions(shared.VINES,['is_shell','is_airborne'],env)
    hero.selected_class(shared.VINES,['needs_support'],'VineSupport',env)
    hero.selected_class(shared.SEPTEMBER,['needs_support'],'Support',env)
    hero.selected_class(CONTENT70,['invulnerable'],'Protection70',env)
    hero.selected_class(CONTENT,['edible'],'Edible',env)
    hero.selected_class(SECRETS,['lantern','stone_wears'],'Secrets',env)
    hero.selected_class(shared.BATTLE,['_star_target'],'Star',env)
    hero.selected_class(PERIODIC,['_wrap_queries'],'PeriodicQueries',env)
    def closure(path,name):
        found=[node for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))) if isinstance(node,ast.FunctionDef) and node.name==name]
        node,=found
        return compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec')
    env['support70']=closure(CONTENT70,'needs_support')
    env['wind']=closure(FLYING,'wind_target')
    tree=ast.parse(CONTENT.read_text(encoding='utf8'))
    pitcher,=[node.value for node in ast.walk(tree) if isinstance(node,ast.Assign) and isinstance(node.value,ast.Lambda)
              and any(isinstance(item,ast.Constant) and item.value=='_pvp_pitcher_columns' for target in node.targets for item in ast.walk(target))]
    env['pitcher']=compile(ast.Expression(pitcher),str(CONTENT),'eval')
    env['region']=marshal.loads(RAW.read_bytes())
    ref['plant_region']=env
    return ref


class PlantRegionExtension(res.ResourceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.plant_seen=False;env=ref['plant_region'];self.plant_ref=env;b=self.b;g=self.g
        support=env['Support']();support.g=g
        vines=env['VineSupport']();vines.g=g;vines._support=support.needs_support
        local=dict(env,g=g,support=vines.needs_support);exec(env['support70'],local)
        g['_pvp_needs_plant_support']=local['needs_support']
        inv=env['Protection70']();inv.b=b
        edible=env['Edible']();edible.g=g;edible.pvp70=inv;g['_pvp_content_edible']=edible.edible
        local=dict(env,self=types.SimpleNamespace(g=g));exec(env['wind'],local);g['_pvp_flying_wind_target']=local['wind_target']
        g['_pvp_pitcher_columns']=eval(env['pitcher'],dict(g=g))
        self.plant_secrets=env['Secrets']();self.plant_secrets.secrets=set()
        g['_pvp66_lantern']=self.plant_secrets.lantern;g['_pvp66_stone_wears']=self.plant_secrets.stone_wears
        self.ns[shooting.P+'starfruit_target']=env[shooting.P+'starfruit_target']
        # _wrap_queries also preserves the existing tripea query. Only star
        # selection is invoked by this native wordcode region.
        periodic=env['PeriodicQueries']._wrap_queries
        periodic(b.periodic_targets,b)
        g['_pvp_star_target']=types.MethodType(env['Star']._star_target,b)
        def gate():
            self.render_log.append(['plant',g['l']]);self.before('plant_gate');self.after('plant_gate')
        g['_pvp_plant_gate']=gate
        spawn=types.FunctionType(ctx.functions['新增僵尸'],g)
        def summon(name,point,facing):
            spawn(name,point,facing);self.units.append(g['僵尸'][-1])
        g['新增僵尸']=summon

    def operation(self,op):
        name=op['op'];g=self.g
        if name=='plant_region_setup':
            self.plant_seen=True
            g.update(金属=op['metal'],boss=op['bosses'],钱币=[],冻住=op.get('freeze',0.),
                     拿中玉米炮=[] if op['selected'] is None else op['selected'],sby=op['pointer'][0],sbx=op['pointer'][1],
                     拿中=op['held'],种植=op['placement'],大波=op['wave'],雨=copy.deepcopy(op['rain']),
                     shui=op.get('water_offset',0.),zbspeedmax=op['speed'],离玩家最近=op.get('nearest',-1))
            self.plant_secrets.secrets={'secret:光疗'} if op.get('lantern') else set()
        elif name in ('plant_fields','plant_unit','plant_entity'):
            objects={'plant_fields':self.all_plants,'plant_unit':self.units,'plant_entity':self.births}[name]
            key={'plant_fields':'plant','plant_unit':'unit','plant_entity':'entity'}[name]
            obj=objects[op[key]];obj.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):obj.pop(key,None)
        elif name=='plant_query':
            query=op['query'];g['l' if query in ('star','support') else 'z']=op['index']
            return g[{'star':'_pvp_star_target','support':'_pvp_needs_plant_support','edible':'_pvp_content_edible','wind':'_pvp_flying_wind_target'}[query]]()
        elif name=='plant_wind':
            if op['after']:self.shoot_wind.after_plants()
            else:self.shoot_wind.before_plants()
        elif name=='plant_region_run':
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants'):
                    exec(self.plant_ref['region'],g)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.plant_seen:
            row['plant_region']=dict(coins=self.g['钱币'],rain=self.g['雨'],freeze=self.g['冻住'],placement=self.g['种植'],suns=self.g['阳光球'],
                                     units=[{key:u[key] for key in UNIT_FIELDS if key in u} for u in self.units])


def cases():
    prototype=res.phase.cases()[0][1];out=[]
    definitions=shared.ROOT/'extract/original/regions/definitions.py'
    tree=ast.parse(definitions.read_text(encoding='utf8'))
    declaration,=[node for node in tree.body if isinstance(node,ast.Assign) and any(getattr(target,'id',None)=='金属' for target in node.targets)]
    constants={};exec(compile(ast.Module(body=[declaration],type_ignores=[]),str(definitions),'exec'),constants)
    metal=constants['金属'];bosses=hero.constant(shooting.plants.TABLES,'boss')
    flying=hero.constant(FLYING_CATALOG,'PLANTS')
    def setup(index):
        case=copy.deepcopy(prototype);case['seed']=920000+index
        case['world_rules'].update(rage=False,deathmatch=False,dense=False)
        case['plant_world'].update(day='夜晚',sky='蓝天',imitation='向日葵')
        ops=case['operations']=case['operations'][:1]
        ops[0].update(mode='duo',rows=[[7,[4,5,6,8,18]],[8,[3,4,5,6,7]]],cols=[[5,[8]],[6,[8]],[18,[7]]])
        ops.append(dict(op='plant_region_setup',air=['幽灵辣椒']+list(flying),flying=flying,metal=metal,bosses=bosses,
                        pointer=[8,5],held='',selected=None,wave=0.,placement='',rain=[[5.,6.,0.,1.]],speed=10.,nearest=0,lantern=index%2==0))
        for i in range(4):
            ops.append(dict(op='plant_unit',unit=i,fields={'_pvp_owner':'zombie','_pvp_content':'','_pvp_variant':'',
                '血量':1000.,'位置':[240.+i*24.,432.,1.,0.],'方向':-1.,'大小':2.,'出场':500.,'手持':'','防具':'',
                '手持血量':0.,'防具血量':0.,'出场初位置':[250.,100.],'出场末位置':[264.,432.]},erase=['魅惑']))
        return case,ops
    def plant(ops,kind='豌豆射手',cell=(8,5),fields=None,facing=1.):
        index=sum(op['op']=='plant_original' for op in ops)
        ops += [dict(op='plant_original',cell=list(cell),name=kind,facing=facing),
                dict(op='plant_fields',plant=index,fields=dict({'_pvp_owner':'plant'},**(fields or {})),erase=['睡觉'])]
        return index
    kinds=('花盆','玉米加农炮','大蒜','窝瓜','大喷菇','雷蘑菇','小喷菇','胆小菇','海蘑菇','裂荚射手','豌豆射手','寒冰射手',
           '双发射手','杨桃','仙人掌','机枪射手','香蒲','地刺','地刺王','萝卜伞','大嘴花','龙蒺藜','忧郁蘑菇',
           '卷心菜投手','玉米投手','西瓜投手','冰瓜投手','路灯花','金盏花','磁力菇','吸金磁','寒冰菇','模仿者',
           '墓碑吞噬者','三叶草','土豆地雷','阳光菇','向日葵','双子向日葵','毁灭菇','樱桃炸弹','火爆辣椒','石果子')
    shooters={'大喷菇','雷蘑菇','小喷菇','胆小菇','海蘑菇','裂荚射手','豌豆射手','寒冰射手','双发射手','杨桃','仙人掌','机枪射手',
              '香蒲','地刺','地刺王','萝卜伞','大嘴花','龙蒺藜','忧郁蘑菇','卷心菜投手','玉米投手','西瓜投手','冰瓜投手'}
    for k,kind in enumerate(kinds):
        for i in range(12):
            case,ops=setup(k*12+i);fields={'根动画':(0.,124.,249.,250.)[i%4],'受伤':(0.,1.,48.,49.)[i//3]}
            secrets=['小喷','水兵','胆大','黄油','卷心菜','大帝','磁力'] if i%3==0 else []
            case['globals']['秘籍']=secrets;case['heroes']['plant']['秘籍']=secrets
            if kind in shooters:
                fields.update(射=(0.,1.,19.,24.,49.,74.,99.,119.,149.,199.,0.,0.)[i],射cd=(-1.,0.,1.,49.,99.,149.,199.,499.,1199.,2.,0.,-1.)[i])
            if kind=='玉米加农炮':fields.update(发射动画=(0.,249.,499.)[i%3],发射闪闪=199.,发射cd=(0.,1.)[i%2],发射x=10.)
            if kind=='裂荚射手':fields.update(副射=(0.,49.)[i%2],副射cd=(-1.,0.,1.)[i%3],副双发=i%2)
            if kind=='胆小菇':fields['胆小']=(0.,1.,99.,100.)[i%4]
            if kind in ('向日葵','双子向日葵','阳光菇','路灯花','金盏花'):
                fields['爆了']=(0.,124.,250.)[i%3]
                if kind=='路灯花':fields['路灯']=(1.,600.)[i%2]
                elif kind=='金盏花':fields['钱钱']=(1.,5000.)[i%2]
                else:fields['阳光']=(1.,0.)[i%2]
            if kind=='阳光菇':fields.update(成长=(1.,0.,2.)[i%3],长大=(0.,1.,199.,200.)[i%4])
            if kind in ('寒冰菇','毁灭菇','樱桃炸弹','火爆辣椒','三叶草'):fields['消亡']=(0.,199.,499.)[i%3]
            if kind in ('磁力菇','吸金磁'):fields['吸']=(0.,1.,2.)[i%3]
            if kind=='墓碑吞噬者':fields['滚蛋']=(0.,99.,999.)[i%3]
            if kind=='土豆地雷':fields.update(埋藏=(0.,1.,2.)[i%3],出来=(0.,59.,119.,179.)[i%4])
            if kind=='模仿者':fields.update(模仿cd=(0.,1.,2.)[i%3],模仿=('豌豆射手','模仿者','普通僵尸','飞贼僵尸')[i%4])
            plant(ops,kind,fields=fields,facing=(-1.,1.)[i%2])
            if kind=='玉米加农炮' and i%2:ops.append(dict(op='plant_fields',plant=0,fields={'黑白':0}))
            if kind=='路灯花':
                for j,other in enumerate(('南瓜头','南瓜头','豌豆射手','大蒜')):plant(ops,other,(8,6+j),{'植物血':1.})
            if kind=='墓碑吞噬者':ops.append(dict(op='tile_replace',cell=[8,5],value={'方块':'坟墓','坟墓':1,'植物':True}))
            if kind in ('磁力菇','吸金磁','雷蘑菇','三叶草'):
                for j,hand in enumerate(('报纸','气球','矿镐','钢门')):
                    ops.append(dict(op='plant_unit',unit=j,fields={'手持':hand,'手持血量':100.,'防具':'铁桶','防具血量':100.}))
            if kind=='萝卜伞':
                ops.append(dict(op='service_entity',name='篮球',position=[264.,390.,1.,2.]))
                ops.append(dict(op='plant_unit',unit=0,fields={'僵尸':'飞贼僵尸'},erase=['离开']))
            ops += [dict(op='plant_region_run') for _ in range(4)]
            out.append(('native-plant-family-'+str(k)+'-'+str(i),case))
    for i in range(96):
        case,ops=setup(1000+i)
        kind=('南瓜头','模仿者','豌豆射手','海蘑菇')[i%4]
        fields={'_pvp_content':('阳光藤蔓','忧郁藤蔓','水盆','抓人草触手','','幽灵辣椒')[i//4%6]}
        if kind=='模仿者':fields['_pvp_copy_card']=('plant:抓人草','plant:旋转芜菁','plant:幽灵辣椒')[i//4%3]
        plant(ops,kind,fields=fields)
        plant(ops,'模仿者' if i%3 else '豌豆射手',fields={'_pvp_content':'旋转芜菁' if i%3==0 else '',
              '_pvp_copy_card':'plant:芦笋战机','植物血':0. if i//24%2 else 6.,'模仿cd':10.})
        if i//48:ops.append(dict(op='plant_fields',plant=1,fields={'死':0}))
        ops += [dict(op='tile_replace',cell=[9,5],value={'方块':'空'}),dict(op='plant_query',query='support',index=0),dict(op='plant_region_run')]
        out.append(('installed-support-chain-'+str(i),case))
    for i in range(96):
        case,ops=setup(1200+i)
        plant(ops,'杨桃',(8,(0,19,5)[i%3]),{'射cd':0.},(-1.,1.)[i%2])
        for j in range(4):
            ops.append(dict(op='plant_unit',unit=j,fields={'位置':[(24.,936.,264.)[i%3]+(-1.,1.)[i%2]*(12.+j*20.),
                (408.,440.,500.,550.)[i//6%4],0.,0.],'血量':0. if j<i%4 else 100.,'大小':(.5,1.,2.,4.)[j]}))
        ops += [dict(op='roster_replace',targets=[0,1,2,3,'zombie','zombie2']),dict(op='plant_query',query='star',index=0),
                dict(op='track_begin',plant=0),dict(op='plant_query',query='star',index=0),dict(op='plant_region_run'),dict(op='track_restore')]
        out.append(('star-rays-periodic-and-heads-'+str(i),case))
    for i in range(64):
        case,ops=setup(1400+i)
        plant(ops,('大嘴花','龙蒺藜')[i%2],fields={'射':74.,'射cd':10.})
        for j in range(4):
            ops.append(dict(op='plant_unit',unit=j,fields={'_pvp_content':('','红眼巨人','普通自定义','')[j],
                '_pvp_variant':'角斗士巨人' if j==3 else '', '_pvp_anchor_until':(0.,1.)[i%2],'大小':(.5,2.,4.,8.)[i//2%4]}))
        ops += [dict(op='plant_query',query='edible',index=j) for j in range(4)]
        ops += [dict(op='plant_region_run'),dict(op='clock',tick=1,time=.004),dict(op='plant_fields',plant=0,fields={'射':74.,'射cd':10.,'吃':0.}),dict(op='plant_region_run')]
        out.append(('chomper-content-anchor-and-boss-'+str(i),case))
    for i in range(48):
        case,ops=setup(1600+i)
        plant(ops,('杨桃','裂荚射手','豌豆射手','玉米投手')[i%4],fields={'射':119. if i%4==3 else 0.,'射cd':100. if i%4==3 else 0.})
        plant(ops,('杨桃','裂荚射手','豌豆射手','玉米投手')[i%4],(8,6))
        ops.append(dict(op='lifecycle_hook',name=('add','plant_gate')[i//4%2],body=[dict(op='plant_roster_replace',plants=[1,0]),dict(op='source_observe')],
                        fail_before=i//8%3==0,fail_after=i//8%3==1))
        ops += [dict(op='plant_region_run',catch=True),dict(op='owner'),dict(op='plant_region_run',catch=True)]
        out.append(('plant-callback-live-roster-and-unwind-'+str(i),case))
    for i in range(64):
        case,ops=setup(1800+i)
        plant(ops,'三叶草',fields={'消亡':(0.,498.)[i%2]},facing=(-1.,1.)[i//2%2])
        for j,name in enumerate(('豌豆','芜菁球弹','篮球','任意无伤实体')):
            ops.append(dict(op='service_entity',name=name,position=[(240.,264.,288.,288.)[j],400.,(-1.,0.,1.,0.)[j],0.]))
            ops.append(dict(op='plant_entity',entity=j,fields={'_pvp_flying56':j%2==i%2}))
            ops.append(dict(op='plant_query',query='wind',index=j))
        for j,hand in enumerate(('气球','报纸','','气球')):
            ops.append(dict(op='plant_unit',unit=j,fields={'位置':[(240.,264.,288.,264.)[j],432.,(-101.,-100.,0.,101.)[i//4%4],0.],
                '手持':hand,'手持血量':10.,'大小':(.5,1.,2.,4.)[j]}))
        ops.append(dict(op='roster_replace',targets=[0,1,2,3,'zombie','zombie2']))
        for _ in range(3):ops += [dict(op='plant_wind',after=False),dict(op='plant_region_run'),dict(op='plant_wind',after=True)]
        out.append(('blover-flight-membership-and-speed-limits-'+str(i),case))
    for i in range(64):
        case,ops=setup(2000+i)
        kind=('海蘑菇','小喷菇','花盆','豌豆射手')[i%4]
        plant(ops,kind,fields={'睡觉':(49.,99.,149.,399.)[i//4%4],'受伤':(0.,49.)[i//16%2]})
        if i//32:
            case['globals']['秘籍']=['水兵'];case['heroes']['plant']['秘籍']=['水兵']
        # plant() deliberately admits awake records. Restore sleeping state
        # here to exercise all three emissions and the 400-tick wrap.
        ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':(49.,99.,149.,399.)[i//4%4]}))
        ops += [dict(op='plant_region_run') for _ in range(3)]
        out.append(('sleeping-support-and-emission-clocks-'+str(i),case))
    for i in range(24):
        case,ops=setup(2200+i)
        for j,kind in enumerate(('向日葵','双子向日葵','阳光菇','机枪射手','卷心菜投手','忧郁蘑菇')):
            plant(ops,kind,(8,2+j),{'阳光':1.,'爆了':0.} if j<3 else None,facing=(-1.,1.)[i%2])
        for count in (126,125,250,250):ops.append(dict(op='batch',body=[dict(op='plant_region_run') for _ in range(count)]))
        out.append(('continuous-mixed-plant-roster-'+str(i),case))
    for i in range(64):
        case,ops=setup(2400+i)
        kind=('大喷菇','雷蘑菇','地刺','地刺王','忧郁蘑菇','寒冰菇','大嘴花','龙蒺藜')[i%8]
        fields={'射cd':100.}
        if kind=='寒冰菇':fields['消亡']=199.
        else:fields['射']=149. if kind in ('大喷菇','雷蘑菇') else 74. if kind in ('大嘴花','龙蒺藜') else 49.
        plant(ops,kind,fields=fields)
        for seat in ('zombie','zombie2'):
            case['heroes'][seat]['玩家位置']=[264.,432.,1.,0.]
            case['heroes'][seat]['玩家血量']=40.;case['players'][seat]['hp']=40.
        ops += [dict(op='roster_replace',targets=['zombie','zombie2',0,1]),
                dict(op='plant_region_run'),dict(op='plant_fields',plant=0,fields=fields),dict(op='plant_region_run')]
        out.append(('native-plant-hero-proxy-and-attack-budget-'+str(i),case))
    for i in range(24):
        case,ops=setup(2600+i)
        kind=('杨桃','豌豆射手','仙人掌','小喷菇','裂荚射手','玉米投手')[i%6]
        plant(ops,kind,fields={'射':119. if kind=='玉米投手' else 0.,'射cd':100. if kind=='玉米投手' else 0.})
        ops.append(dict(op='service_entity',name='星星',position=[264.,400.,1.,0.]))
        ops.append(dict(op='lifecycle_hook',name='add',body=[dict(op='squash_roster',entities=[] if i//6%2 else [0])]))
        ops += [dict(op='plant_region_run',catch=True),dict(op='plant_region_run',catch=True)]
        out.append(('constructor-replaces-entity-tail-'+str(i),case))
    return out


def paths():
    return [Path(__file__).resolve(),Path(res.__file__),Path(res.hp.__file__),Path(res.phase.__file__),Path(shared.__file__),
            shared.BATTLE,shared.SEPTEMBER,shared.VINES,FLYING,FLYING_CATALOG,CONTENT,CONTENT70,CATALOG70,SECRETS,PERIODIC,RAW,
            shared.ROOT/'tools/typed72/plant_region_probe.cpp',shared.ROOT/'tools/typed72/resources_probe.cpp',
            shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,PlantRegionExtension,'typed72-installed-plant-region',probe_timeout=600))
