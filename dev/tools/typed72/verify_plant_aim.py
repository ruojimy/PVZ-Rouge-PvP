"""Literal periodic tripea selection, pea hybrid source gate and projectile constructor wrapper."""
import ast
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_plant_region as plants
shared=plants.shared
shooting=plants.shooting
hero=plants.hero
EXPANSION=shared.PVP/'native_expansion.py'


def reference():
    ref=plants.reference()
    env=dict(math=math)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    hero.selected_class(EXPANSION,['_aim_pea'],'Hybrid',env)
    for name in ('IMP_BLACK_ARMOR','BLACK_ARMOR_DROP'):env[name]=hero.constant(EXPANSION,name)
    shooting.projectiles.functions(EXPANSION,['worn_black_armor'],env)
    tree=ast.parse(EXPANSION.read_text(encoding='utf8'))
    projectile,=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='projectile']
    env['projectile']=compile(ast.Module(body=[projectile],type_ignores=[]),str(EXPANSION),'exec')
    ref['plant_aim']=env
    return ref


class PlantAimExtension(plants.PlantRegionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.hybrid_seen=False
        env=ref['plant_aim'];b=self.b;g=self.g
        b.expansion._aim_pea=types.MethodType(env['Hybrid']._aim_pea,b.expansion)
        local=dict(env,self=b.expansion,battle=b,add=g['新增实体'])
        exec(env['projectile'],local)
        g['新增实体']=local['projectile']

    def operation(self,op):
        name=op['op'];b=self.b;g=self.g
        if name=='hybrid_setup':
            self.hybrid_seen=True
            b.team_secrets['plant']={'secret:豌豆杂交'} if op['enabled'] else set()
        elif name=='hybrid_fields':
            plant=self.all_plants[op['plant']];fields=op['fields']
            if 'angle' in fields:plant['_pvp_pea_angle']=fields['angle']
            if 'split' in fields:
                plant['_pvp_split_pea_angles']=None if fields['split'] is None else {int(k):v for k,v in fields['split'].items()}
        elif name=='hybrid_gate':
            try:b.expansion.source_gate(None if op['plant'] is None else self.all_plants[op['plant']])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='hybrid_query':
            result=self.ns[shooting.P+'pick_tripea_targets'](g,self.all_plants[op['plant']],op['centers'])
            return [[t[0],self.label(t[1]),list(t[2])] if t is not None else None for t in result]
        elif name=='hybrid_birth':
            try:
                with self.c.context('zombie','plant','plants',self.all_plants[op['plant']]):
                    g['新增实体'](op['name'],op['facing'],list(op['point']))
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='hybrid_region':
            original=g['_pvp_plant_gate']
            def gate():
                original()
                b._tracking_gate()
            g['_pvp_plant_gate']=gate
            try:
                with self.c.context('zombie','plant','plants'):
                    try:exec(self.plant_ref['region'],g)
                    finally:
                        b.expansion.source_gate(None)
                        b.periodic_targets.restore()
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
            finally:g['_pvp_plant_gate']=original
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.hybrid_seen:return
        row['hybrid_active']=self.b.expansion.saved_rows is not None
        for key in ('plants','all_plants'):
            row[key]=copy.deepcopy(row[key])
            for plant in row[key]:
                if isinstance(plant.get('_pvp_split_pea_angles'),dict):
                    plant['_pvp_split_pea_angles']={str(k):v for k,v in plant['_pvp_split_pea_angles'].items()}


def cases():
    prototype=plants.cases()[0][1];output=[]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=980000+i
        ops=case['operations']=case['operations'][:2]
        ops[0].update(mode='duo',rows=[[8,[]],[3,[1,9]]],cols=[])
        ops.append(dict(op='hybrid_setup',enabled=True))
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'血量':100.,'位置':[312.+unit*48.,432.,0.,0.],
                        '_pvp_owner':'zombie','大小':2.},erase=['魅惑']))
        return case,ops
    def plant(ops,kind='豌豆射手',cell=(8,5),facing=1.,fields=None):
        index=sum(op['op']=='plant_original' for op in ops)
        ops.extend([dict(op='plant_original',cell=list(cell),name=kind,facing=facing),
                    dict(op='plant_fields',plant=index,fields=dict({'_pvp_owner':'plant'},**(fields or {})),erase=['睡觉'])])
        return index
    for i in range(128):
        case,ops=setup(i)
        x=(24.,936.,264.,-24.)[i%4]
        plant(ops,cell=(8,int(x//48)),facing=(-1.,0.,1.,2.)[i//4%4])
        for j in range(4):
            fields={'位置':[x+(-1.,-1.0000001,1.,48.)[(i+j)%4],410.+(j%2)*40.,0.,0.],
                    '大小':(None,.2,2.,4.)[(i+j)%4],'血量':0. if i%11==j else 100.}
            if i%7==j:fields['魅惑']=None
            if i%9==j:fields['灰烬']=0.
            ops.append(dict(op='plant_unit',unit=j,fields=fields))
        ops.extend([dict(op='roster_replace',targets=[0,1,0,3,'zombie','zombie2']),
            dict(op='hybrid_query',plant=0,centers=[[x,400.],[x,430.],[x,400.],[x+48.,400.]]),
            dict(op='track_begin',plant=0),dict(op='hybrid_query',plant=0,centers=[[x,400.],[x,400.],[x,400.]]),
            dict(op='track_restore'),dict(op='hybrid_query',plant=0,centers=[])])
        output.append(('tripea-periodic-direction-ties-and-duplicates-'+str(i),case))
    for i in range(128):
        case,ops=setup(200+i)
        kind=('豌豆射手','寒冰射手','双发射手','机枪射手','裂荚射手','向日葵','小喷菇','豌豆射手')[i%8]
        plant(ops,kind,fields={'_pvp_content':('','原始豌豆射手','幽灵辣椒','')[i//8%4]},facing=(-1.,1.)[i//32%2])
        if i%13==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        if i%17==0:ops.append(dict(op='hybrid_setup',enabled=False))
        if i%3:ops.append(dict(op='hybrid_fields',plant=0,fields={'angle':(0.,179.,360.,-350.)[i%4]}))
        for j in range(4):
            ops.append(dict(op='plant_unit',unit=j,fields={'位置':[264.+(-48.,48.)[i//32%2],
                403.2+(48.,48.0000001,-48.,-48.0000001)[i//4%4]+40.32,0.,0.], '血量':100. if j==0 else 0.}))
        ops.extend([dict(op='hybrid_gate',plant=0) for unused in range(4)])
        ops.extend([dict(op='hybrid_birth',plant=0,name='豌豆',facing=1.,point=[264.,400.,.96,0.]),dict(op='hybrid_gate',plant=None)])
        output.append(('hybrid-source-gates-and-angle-clipping-'+str(i),case))
    for i in range(64):
        case,ops=setup(400+i)
        plant(ops,'裂荚射手',cell=(8,19 if i%2 else 0),facing=(-1.,1.)[i%2])
        ops.append(dict(op='hybrid_fields',plant=0,fields={'split':{'1':(-370.,0.,350.,710.)[i%4],'-1':(170.,180.,-170.,540.)[i//4%4]}}))
        for j in range(4):
            ops.append(dict(op='plant_unit',unit=j,fields={'位置':[(-10.,50.,930.,870.)[j],(360.,400.,470.,550.)[i//16],0.,0.]}))
        for unused in range(4):ops.extend([dict(op='hybrid_gate',plant=0),dict(op='hybrid_gate',plant=None)])
        for vx in (-.96,0.,.96):
            ops.append(dict(op='hybrid_birth',plant=0,name='冰豆',facing=1.,point=[24.,400.,vx,.25]))
        output.append(('hybrid-split-independent-heads-and-births-'+str(i),case))
    for i in range(32):
        case,ops=setup(600+i)
        plant(ops,('豌豆射手','裂荚射手','机枪射手','双发射手')[i%4],cell=(8,19 if i%2 else 5),facing=(-1.,1.)[i//4%2])
        plant(ops,'豌豆射手',cell=(8,6))
        for j in range(4):ops.append(dict(op='plant_unit',unit=j,fields={'位置':[24.+j*48.,420.,0.,0.]}))
        ops.extend([dict(op='hybrid_region') for unused in range(4)])
        ops.append(dict(op='batch',body=[dict(op='hybrid_region') for unused in range(200)]))
        output.append(('hybrid-native-roster-and-burst-'+str(i),case))
    for i in range(24):
        case,ops=setup(700+i)
        plant(ops,'裂荚射手' if i%2 else '豌豆射手')
        ops.append(dict(op='hybrid_fields',plant=0,fields={'split':{'1':45.,'-1':150.}} if i%2 else {'angle':45.}))
        ops.append(dict(op='service_entity',name='豌豆',position=[264.,400.,1.,0.]))
        ops.append(dict(op='lifecycle_hook',name='add',body=[dict(op='squash_roster',entities=[] if i//2%2 else [0,0])],
                        fail_before=i//4%3==0,fail_after=i//4%3==1))
        for name in ('豌豆','星星'):
            ops.append(dict(op='hybrid_birth',plant=0,name=name,facing=1.,point=[264.,400.,1.,0.],catch=True))
        output.append(('hybrid-constructor-list-replacement-and-unwind-'+str(i),case))
    for i in range(24):
        case,ops=setup(800+i)
        plant(ops,'裂荚射手' if i%2 else '豌豆射手')
        fields=({'split':None},{'split':{}},{'split':{'1':None}})[i//2%3] if i%2 else {'angle':None}
        ops.extend([dict(op='hybrid_fields',plant=0,fields=fields),dict(op='hybrid_gate',plant=0,catch=True),
                    dict(op='hybrid_birth',plant=0,name='豌豆',facing=1.,point=[264.,400.,-.96,0.],catch=True),
                    dict(op='hybrid_gate',plant=None)])
        output.append(('hybrid-angle-presence-and-exception-state-'+str(i),case))
    return output


def paths():
    return plants.paths()+[Path(__file__).resolve(),Path(plants.__file__),EXPANSION,shared.ROOT/'tools/typed72/plant_aim_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,PlantAimExtension,'typed72-plant-hybrid-aim',probe_timeout=600))
