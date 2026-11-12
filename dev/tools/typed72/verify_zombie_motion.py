"""Compare the mobile zombie body with the installed native wordcode up to displacement."""
import ast
import copy
import dis
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_entity_phase as phase

shared=phase.shared
hero=shared.hero
shooting=shared.shooting
ROOT=shared.ROOT
RAW=ROOT/'extract/live/zombies.marshal'
BITES=shared.PVP/'native_bites.py'
BLACK=shared.PVP/'expansion_catalog.py'
CACTUS=shared.LOCAL/'pvp66_secrets.py'
CONTENT=shooting.projectiles.CONTENT
MOTION_FIELDS=['坚持分兵','分兵','再出场','出场','炸音','中场','苏醒','憋气','跳跃cd','啃咬','移速','大蒜','入水','跳舞',
               '出场初位置','出场末位置','_pvp_bite_plant','_pvp_no_attack']

def body_code():
    native=marshal.loads(RAW.read_bytes())
    instructions={i.offset:i for i in dis.get_instructions(native)}
    # Enter after the per-unit gate callback; execute its displaced LOADs.
    start,end=168864,79050
    assert [(instructions[i].opname,instructions[i].argval) for i in (168858,168866,168868,168874,79048,79052)]==[
        ('LOAD_NAME','_pvp_zombie_gate'),('LOAD_NAME','僵尸'),('LOAD_NAME','l'),('JUMP_ABSOLUTE',68450),
        ('STORE_NAME','wy'),('LOAD_NAME','僵尸')]
    code=bytearray(native.co_code)
    code[:6]=bytes((dis.EXTENDED_ARG,start>>16,dis.EXTENDED_ARG,(start>>8)&255,dis.opmap['JUMP_ABSOLUTE'],start&255))
    code[end:end+4]=bytes((dis.opmap['LOAD_CONST'],native.co_consts.index(None),dis.opmap['RETURN_VALUE'],0))
    for i in instructions.values():
        if 68450<=i.offset<end and (i.opcode in dis.hasjabs or i.opcode in dis.hasjrel):
            assert 68450<=i.argval<=end or i.argval==168832,(i.offset,i.argval)
    return native.replace(co_code=bytes(code))

def reference():
    ref=phase.reference();env={'__package__':shared.PACKAGE,'sys':sys}
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    env['BLACK_ZOMBIES']=hero.constant(BLACK,'BLACK_ZOMBIES')
    env['FLYERS']=('海盗鹦鹉','乌鸦')
    for key in ('CACTUS_REFLECT','CACTUS_NATIVE_SECRET'):env[key]=hero.constant(CACTUS,key)
    hero.selected_class(CACTUS,['cactus'],'Cactus',env)
    hero.selected_class(CONTENT,['barrel_active','plant_bite','bite_damage','flyer_bite_effect'],'Content',env)
    hero.selected_class(shared.BATTLE,['_rally_speed','_ladder_support_request'],'Navigation',env)
    hero.selected_class(hero.ZSECRETS,['bite_rate'],'Secrets',env)
    env['prefix']=body_code()
    def nested(path,name):
        fn,=[n for n in ast.walk(ast.parse(path.read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef) and n.name==name]
        return fn
    # Use actual installed bytecode patch closures and the native code-object
    # identity for the caller-sensitive reciprocal and Dave bite overrides.
    fn=nested(BITES,'install')
    env['bite_functions']=compile(ast.Module(body=[n for n in fn.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),str(BITES),'exec')
    env['STONE_BLACK_BITE']=hero.constant(BITES,'STONE_BLACK_BITE')
    hit=nested(CONTENT,'hit')
    ends=[i for i,n in enumerate(hit.body) if isinstance(n,ast.If) and any(isinstance(s,ast.Constant) and s.value==72380 for s in ast.walk(n))]
    end,=ends
    hit.body=hit.body[:end+1]+[ast.copy_location(ast.parse('return damage(index,facing,amount)').body[0],hit.body[end])]
    fn=nested(CONTENT,'hero_damage')
    env['damage_code']=compile(ast.fix_missing_locations(ast.Module(body=[hit,fn],type_ignores=[])),str(CONTENT),'exec')
    env['predicates']={}
    for path,names in ((CONTENT,['_pvp_fixed_heading','_pvp_charm_alone']),(shared.SEPTEMBER,['_pvp_can_bite_dave'])):
        tree=ast.parse(path.read_text(encoding='utf8'))
        for name in names:
            node,=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Lambda) and
                   any(isinstance(k,ast.Constant) and k.value==name for t in n.targets for k in ast.walk(t))]
            env['predicates'][name]=compile(ast.Expression(node),str(path),'eval')
    mod=sys.modules[shared.PACKAGE+'.native_targets']
    for key in ('HERO_BITE_DAMAGE','HERO_BLACK_BITE_DAMAGE'):setattr(mod,key,hero.constant(phase.TARGETS,key))
    mod.BLACK_BITE_VARIANTS=set(env['BLACK_ZOMBIES'])
    ref['motion']=env
    return ref

class MotionExtension(phase.PhaseExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.motion_seen=False
        env=dict(ref['motion']);self.motion_ref=env;g=self.g;b=self.b
        content=env['Content']();content.g=g;content.b=b
        env.update(content=content,game=g,self=content,b=b,g=g,head_scan_code=None,
                   ns=self.ns,damage=g['伤害僵尸'],hero=self.c._player_damage)
        exec(env['damage_code'],env);exec(env['bite_functions'],env)
        g.update(_pvp_stone_bite=env['stone_bite'],_pvp_plant_bite_bonus_write=lambda:env['bite'](1.),
                 _pvp_frenzy_bite_bonus_write=lambda:env['bite'](3.),伤害僵尸=env['hit'],掉血=env['hero_damage'])
        g['位移处理'].__defaults__=(1,)
        for key,code in env['predicates'].items():g[key]=eval(code,env)
        self.cactus=env['Cactus']();self.cactus.g=g
        g['_pvp66_cactus']=self.cactus.cactus
        b.zsecrets.bite_rate=types.MethodType(env['Secrets'].bite_rate,b.zsecrets)
        for key in ('_rally_speed','_ladder_support_request'):g['_pvp'+key]=types.MethodType(getattr(env['Navigation'],key),b)
        b.engine.regions['zombies']=env['prefix']
        b.director=types.SimpleNamespace(request_ladder=lambda battle,u:self.render_log.append(['ladder',self.unit_index(u)]))
        self.destination=None
        b.rally_for=lambda obj:self.destination
        b.rally_destination=lambda obj:self.destination

    def operation(self,op):
        action=op['op'];g=self.g;b=self.b
        if action=='motion_setup':
            self.motion_seen=True
            self.cactus.secrets={'secret:尖刺'} if op.get('cactus') else set()
            if op.get('charm_secret'):b.team_secrets['plant'].add('secret:魅惑')
            b.scripted=op.get('scripted',False);self.destination=op.get('rally')
            g.update(洪水=[[type(g['ditu'][0])(a) for a in layer] for layer in op['flood']],
                     梯子尸数=op.get('ladders',0),梯子cd=op.get('ladder_cd',0),目标植物=op.get('target',-1),
                     先别追植=op.get('hold',0),大波=op.get('wave',0),paoku=op.get('running',1),boss=op.get('bosses',[]))
            g['分梯']=list(op.get('ladder_cols',[]))
        elif action=='motion_unit':
            self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='motion_body':
            g['l']=op['index'];exec(self.motion_ref['prefix'],g)
            return [g['x'],g['y'],g['zhongxin'],g['hs'],g['不动'],g['可'],g['wy']]
        elif action=='motion_static':
            i=op['index'];u=g['僵尸'][i]
            if (u.get('_pvp_grave') or u.get('_pvp_hero') or u.get('_pvp_orphan_barrel')) and u['血量']>0:
                g['l']=i
                for code in self.motion_ref['static']:exec(code,g)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.motion_seen:row['motion_units']=[{k:u[k] for k in MOTION_FIELDS if k in u} for u in self.units]

def build_ref():
    ref=reference()
    ref['motion']['static']=[marshal.loads((ROOT/('extract/live/'+stem+'.marshal')).read_bytes())
                             for stem in ('zombie_coordinates','zombie_body_index')]
    return ref

def cases():
    template=phase.cases()[0][1]
    out=[]
    def setup(i,kind='普通僵尸',**fields):
        c=copy.deepcopy(template);c['seed']=119200+i;c['operations']=c['operations'][:1];ops=c['operations']
        c['globals'].update(wjx=5.,wjy=8.)
        setup=ops[0];setup['rows']=[];setup['cols']=[]
        cols=len(c['plant_world']['grid'][0]);rows=len(c['plant_world']['grid'])
        nav=dict(op='motion_setup',flood=[[[v]*cols for _ in range(rows)] for v in (i%5,4)],bosses=['巨人僵尸'])
        ops.append(nav)
        for j in range(2):
            vals=dict(僵尸=kind if j==0 else '普通僵尸',出场=500.,炸音=0.,憋气=0.,啃咬=0.,跳跃cd=0.,
                      移速=.349,再出场=1.,坚持分兵=0.,入水=False,大小=2.,位置=[(5.5+j*4)*48.,8.6*48.,.22,-.3])
            if not j:vals.update(fields)
            ops.append(dict(op='motion_unit',unit=j,values=vals))
        ops.append(dict(op='roster_replace',targets=[0,1]))
        return c,ops,nav
    def run(label,c,ops,i,steps=3):
        ops.append(dict(op='context',target='plant',owner='zombie',phase='zombies',body=[dict(op='motion_body',index=0) for _ in range(steps)]))
        out.append((label+'-'+str(i),c))
    for i in range(116):
        kind=('普通僵尸','飞贼僵尸','报纸僵尸','雪人僵尸','潜水僵尸','小鬼僵尸','鸭子僵尸','旗帜僵尸','雪橇车僵尸')[i%9]
        vals=dict(分兵=(0,1,23)[i%3],跳跃cd=i%4,啃咬=(0,1,3,120)[i%4])
        if i%4==0:vals['冰冻']=(1,2,1001,1002)[i//4%4]
        if i%4==1:vals['大蒜']=(1,399,400,401)[i//4%4]
        if i%4==2:vals['黄油']=i%3
        if i%8==3:vals['眩晕']=2.
        if i%8==7:vals['出场']=(498,499,-1)[i//8%3]
        if i%13==0:vals['苏醒']=0
        c,ops,nav=setup(i,kind,**vals)
        nav.update(target=-1 if i%2 else 1,ladder_cols=[5],hold=i%2)
        if i%3==2:
            for row in (7,8):ops.append(dict(op='tile_replace',cell=[row,5],value={'方块':'水'}))
        if i%5==2:ops.append(dict(op='tile_replace',cell=[7,5],value={'方块':'雪'}))
        run('status-and-navigation',c,ops,i)
    for i in range(75):
        kind=('普通僵尸','气球僵尸','梯子僵尸','普通僵尸','飞贼僵尸')[i%5]
        hand=('','气球','梯子','弹跳杆','')[i%5]
        c,ops,nav=setup(i+200,kind,手持=hand,位置=[(34.5+i%3)*48.,412.,-.5,-.1])
        nav.update(wave=1,running=(1,2,3)[i%3],rally=[(34.5+i%3)*48.,412.],scripted=True,ladders=2)
        if i%3==1:ops.append(dict(op='motion_unit',unit=0,values={'中场':0}))
        if i%3==2:ops.append(dict(op='motion_unit',unit=0,values={'_pvp_content':'滚桶僵尸','手持血量':3.}))
        run('offscreen-entry',c,ops,i)
    plants=['豌豆射手','大蒜','石果子','仙人掌','魅惑菇','土豆地雷','缠绕海草','地刺','花盆','大喷菇','向日葵','海蘑菇']
    for i in range(120):
        name=plants[i%len(plants)]
        c,ops,nav=setup(400+i,('普通僵尸','墓碑吞噬者僵尸','飞贼僵尸','巨人僵尸','普通僵尸')[i//12%5])
        nav.update(cactus=i%2==1,charm_secret=i%4==0)
        c['heroes']['plant']['秘籍']=['雷霆','水兵'] if i//12%2 else []
        ops.append(dict(op='plant_original',name=name,cell=[7 if i%4==0 else 8,5]))
        vals={'_pvp_bite_plant':2.5}
        if i//12%5==0:vals.update(_pvp_variant='黑路障僵尸')
        if i//12%5==2:vals.update(_pvp_content='乌鸦')
        if i//12%5==3:vals.update(狂暴=0.)
        if i//12%5==4:vals.update(_pvp_no_attack=True)
        ops.append(dict(op='motion_unit',unit=0,values=vals))
        if name=='石果子':ops.append(dict(op='plant_write',plant=0,values={'消亡':1}))
        if name=='土豆地雷':ops.append(dict(op='plant_write',plant=0,values={'出来':1}))
        run('plant-bite',c,ops,i)
    for i in range(72):
        c,ops,nav=setup(i+600)
        if i%2:
            c['heroes']['plant']['玩家位置'][:2]=[264.,412.8]
            c['heroes']['plant']['模式']='正常模式'
            c['players']['plant']['secrets']=['secret:体香']
        else:
            ops.append(dict(op='motion_unit',unit=0,values={'魅惑':(199,200,3000,9999)[i//2%4]}))
            ops.append(dict(op='motion_unit',unit=1,values={'位置':[269.,412.,.3,0.],'大小':(2,3)[i//6%2]}))
        nav.update(charm_secret=i%3==0)
        vals=[{'_pvp_content':'乌鸦','_pvp_bite_plant':2.8},{'_pvp_variant':'黑普通僵尸'},{'_pvp_no_attack':True},
              {'_pvp_card':'zombie:红眼巨人','狂暴':0.},{'_pvp_no_hero_attack':True},{}][i//4%6]
        ops.append(dict(op='motion_unit',unit=0,values=vals))
        run('hero-and-reciprocal',c,ops,i)
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(phase.__file__),Path(shared.__file__),ROOT/'tools/typed72/world_rules_probe.cpp',ROOT/'tools/typed72/zombie_motion_fixture.inc',
           RAW,BITES,BLACK,CACTUS,shared.BATTLE,CONTENT,shared.SEPTEMBER,shared.PLANT_ZOMBIES,phase.PERIODIC,phase.EXPANSION,
           ROOT/'extract/live/zombie_coordinates.marshal',ROOT/'extract/live/zombie_body_index.marshal']
    sys.exit(shooting.main(paths,build_ref,cases,MotionExtension,'typed72-zombie-motion'))
