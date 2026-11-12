"""Compare the installed physics slices and seat selection against typed hero movement."""
import copy
import importlib
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_entity_phase as phase
shared=phase.shared
shooting=shared.shooting
hero=shared.hero

def reference():
    ref=phase.reference()
    module=importlib.import_module(shared.PACKAGE+'.native_physics')
    proto=module.NativePhysics(ref['world_rules']['root'],{},periodic=True)
    ref['hero_physics']=proto
    return ref

class HeroPhysicsExtension(phase.PhaseExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.physics=copy.copy(ref['hero_physics'])
        g=self.g;self.physics.g=g
        module=sys.modules[shared.PACKAGE+'.native_physics']
        original=self.raw['位移处理'];original.__defaults__=(1,)
        g.update(__native_displacement=original,__native_original_out=g['出界'],__native_original_open_top=g['不封顶出界'],
                 位移处理=types.FunctionType(module._capture_displacement.__code__,g,'位移处理',(1,)),
                 抖=types.FunctionType(ctx.functions['抖'],g),水='水')
    def operation(self,op):
        name=op['op']
        if name=='hero_make':
            self.b.avatars[op['side']]=self.physics.make_state(*op['point'],mode=op['mode'],hp=op['hp'],secrets=op['secrets'])
            self.b.hero_states[op['side']]=self.b.avatars[op['side']]
        elif name=='hero_step':
            self.physics.step(self.b.avatars[op['side']],op['move'],op['held'],op['press'],op['cap'],op['balloon_hp'])
        elif name=='hero_effects':
            self.g['离玩家最近']=op.get('nearest',-1)
            self.physics.advance_hero_effects(self.b.avatars[op['side']],op['tail'])
        else:return super().operation(op)

def cases():
    src=phase.cases()[0][1];out=[]
    def setup(i):
        c=copy.deepcopy(src);c['seed']=425720+i
        c['operations']=c['operations'][:1]
        return c,c['operations']
    def make(ops,side,p,mode,hp,secrets):
        ops.append(dict(op='hero_make',side=side,point=list(p),mode=mode,hp=hp,secrets=secrets))
    def step(side,move=0,held=False,press=False,cap=2,balloon=10):
        return dict(op='hero_step',side=side,move=move,held=held,press=press,cap=cap,balloon_hp=balloon)
    def effects(side,tail,near):
        return dict(op='hero_effects',side=side,tail=tail,nearest=near)
    for i in range(144):
        c,ops=setup(i)
        tile=c['plant_world'].get('tile',48.);w=len(c['plant_world']['grid'][0])*tile
        x=(tile*5.5,-.5,w+.25,w-2.)[i%4];y=(8.5,8.98,.2,9.05)[i//4%4]*tile
        s=('plant','zombie','plant2','zombie2')[i%4]
        make(ops,s,(x,y),'正常模式' if i%2==0 else '我是僵尸',12. if i%3 else 40.,['疾行'] if i%4 else [])
        pos=[x,y,(-1.,0.,1.)[i%3],(-2.,.5,1.)[i//3%3]]
        ops.append(dict(op='write',target=s,values={'玩家位置':pos,'玩家跳跃':i//2%4,'二段跳':(0,1,98,99)[i//4%4],'冻水':i%2}))
        col=int((x%w)//tile)
        for row,block in ((8,('水','梯子块','空')[i//2%3]),(7,('雪','水','空')[i//3%3])):
            ops.append(dict(op='tile_replace',cell=[row,col],value={'方块':block}))
        for j in range(5):
            ops.append(step(s,(-1,0,1)[(i+j)%3],i%3!=1,(i+j)%2==0,1+(i//6)%3))
        out.append(('seat-environment-and-jumps-'+str(i),c))
    for i in range(112):
        c,ops=setup(200+i);s=('plant','zombie')[i%2]
        make(ops,s,(264.,405.),'正常模式',(0.,1.,10.,11.,12.,13.,40.)[i%7],[])
        ops.append(dict(op='write',target=s,values={'玩家倒地':(1,2,89,90)[i%4],'玩家恢复':(0,1998,1999,2000,2001)[i//2%5],
                        '冻水':i%2,'气球':(-1,0,1,98,99)[i//3%5],'辣飞天':(0,1,15,16)[i//5%4]}))
        for j in range(4):
            ops.append(step(s,1,True,True,3,12 if i%2 else 10));ops.append(effects(s,True,-1))
        out.append(('recovery-chili-and-balloon-'+str(i),c))
    for i in range(88):
        c,ops=setup(400+i)
        for j,s in enumerate(('plant','zombie2')):
            make(ops,s,(264.+j*240.,405.),'我是僵尸' if j else '正常模式',40.,['猫尾'])
            ops.append(dict(op='write',target=s,values={'猫尾':(0,48,49,98,99)[(i+j)%5],'猫尾cd':(0,149,299,449,999)[i//2%5],
                    '猫尾摇摆':(0,248,249)[(i+j)%3],'玩家方向':1 if j else -1,'气球':(0,1,98,99)[i%4]}))
        for j in range(3):
            for s in ('plant','zombie2'):
                ops.append(effects(s,(i+j)%3!=1,0 if i%2==0 else -1))
        out.append(('two-seat-ability-order-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(phase.__file__),Path(shared.__file__),shared.ROOT/'tools/typed72/world_rules_probe.cpp',
           shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',shared.BATTLE,hero.PHYSICS,phase.PERIODIC,phase.EXPANSION,
           shared.PVP/'native_bytecode.py',shared.PVP/'native_gate.py']
    sys.exit(shooting.main(paths,reference,cases,HeroPhysicsExtension,'typed72-hero-physics-and-effects'))
