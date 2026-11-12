"""Full native reverse zombie region with installed numeric PvP gates and observed per-body gate."""
import ast
import contextlib
import copy
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_zombie_motion as motion
phase=motion.phase
shared=motion.shared
shooting=motion.shooting
hero=motion.hero
MINER=shared.PVP/'pvp56_zombies.py'
ACTION_FIELDS=('坚持分兵','再出场','出场','炸音','中场','跳舞cd','灯光','前进','篮球cd','篮球总量','投篮','撞车','轮子','雪容量','丢小鬼','苏醒','红眼','半血',
               '憋气','跳跃cd','啃咬','移速','出土','离开','旋转','别消失','手持动画','篮球','_pvp_miner_rally')

def reference():
    r=motion.build_ref();env=dict(contextmanager=contextlib.contextmanager)
    hero.selected_class(motion.CONTENT,['_install_plant_visual_lifecycles','plant_art'],'PlantArt',env)
    hero.selected_class(MINER,['miner_goal','miner_row','rally_miner','alive'],'Miner',env)
    hero.selected_class(hero.ZSECRETS,['movement_factor'],'Secrets',env)
    tree=ast.parse(motion.CONTENT.read_text(encoding='utf8'))
    cart=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ('cart_ammo_death','cart_ammo_reload')]
    assert len(cart)==2
    env['cart']=compile(ast.Module(body=cart,type_ignores=[]),str(motion.CONTENT),'exec')
    speed,=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Lambda) and
            any(isinstance(s,ast.Constant) and s.value=='_pvp_car_speed' for t in n.targets for s in ast.walk(t))]
    env['speed']=compile(ast.Expression(speed),str(motion.CONTENT),'eval')
    env['code']=marshal.loads(motion.RAW.read_bytes());r['actions']=env
    return r

class ActionExtension(motion.MotionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.action_seen=False;self.flat_sequence=10000
        g=self.g;b=self.b;r=ref['actions'];b.engine.regions['zombies']=r['code']
        b.zsecrets.movement_factor=types.MethodType(r['Secrets'].movement_factor,b.zsecrets)
        env=dict(g=g,b=b);exec(r['cart'],env)
        g.update(_pvp_cart_ammo_death=env['cart_ammo_death'],_pvp_cart_ammo_reload=env['cart_ammo_reload'],
                 _pvp_car_speed=eval(r['speed'],env),bi=g['比']/810.,黑色=(0,0,0))
        miner=r['Miner']();miner.b=b;miner.g=g
        g['_pvp56_miner_goal']=miner.miner_goal;g['_pvp56_miner_row']=miner.miner_row
        g['哪个无南瓜植物']=lambda y,x:self.vines.lookup(y,x,True)
        g['抖']=types.FunctionType(ctx.functions['抖'],g)
        spawn=types.FunctionType(ctx.functions['新增僵尸'],g)
        def summon(name,pos,direction):
            spawn(name,pos,direction);self.units.append(g['僵尸'][-1])
        g['新增僵尸']=summon
        original=types.FunctionType(ctx.functions['扁死'],g)
        def crush(row,col):
            count=len(self.births);result=original(row,col)
            if len(self.births)>count:
                sprite=self.births[-1]['扁']
                self.render_log.append(['flat',sprite.key,sprite.size,sprite.flip])
                self.flat_sequence+=1;sprite.key=self.flat_sequence
            return result
        g['反']=lambda s:self.surface(s.key,not s.flip,s.size)
        g['扁死']=crush
        art=r['PlantArt']();art.g=g;art.b=b;art._install_plant_visual_lifecycles()
        g['画线']=lambda black,start,end:self.render_log.append(['line',start,end])
        g['摄像裁剪显示']=lambda sprite,pos,rect:self.render_log.append(['crop',sprite.key,list(pos),sprite.flip,list(rect[2:])])
        g['_pvp_zombie_gate']=lambda:self.render_log.append(['zombie',g['l']])

    def operation(self,op):
        g=self.g
        if op['op']=='action_setup':
            self.action_seen=True;g.update(大尸=list(op.get('large',[])),爆币=op.get('coin_count',0),钱币=[],补帧=0 if op.get('draw') else 1)
        elif op['op']=='zombie_run':exec(self.b.engine.regions['zombies'],g)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.action_seen:
            # Smoke uses an RGBA tuple and sampled sprites use lists. JSON
            # carries both as arrays; retain and compare every channel.
            row['particle_state']=[[list(color),pos,age] for color,pos,age in row['particle_state']]
            row['action_units']=[{k:u[k] for k in ACTION_FIELDS if k in u} for u in self.units]
            row['coin_count']=self.g['爆币'];row['coins']=self.g['钱币']

def cases():
    prototype=motion.cases()[1][1];out=[]
    def setup(i,kind='普通僵尸',values=None):
        c=copy.deepcopy(prototype);c['seed']=720200+i;ops=c['operations']=c['operations'][:5]
        ops[-1]=dict(op='roster_replace',targets=[0])
        c['globals']['wjx']=5.;c['heroes']['plant']['wjx']=5.;c['heroes']['plant']['wjy']=8.
        vals=ops[2]['values']
        for k in ('大蒜','冰冻','黄油','眩晕','分兵'):vals.pop(k,None)
        vals.update(僵尸=kind,方向=-1,位置=[264.,412.8,1.,0.],啃咬=0.,跳跃cd=0.,炸音=0.,出场=500.,移速=.4,大小=2.,入水=False,
                    出场初位置=[120.,100.],出场末位置=[264.,412.8])
        vals.update(values or {})
        ops.append(dict(op='action_setup',draw=i%2==0,large=['巨人僵尸','雪橇车僵尸','投篮车僵尸'],coin_count=i%5))
        return c,ops
    def run(c,ops,label,i,steps=3):
        ops.append(dict(op='context',target='plant',owner='zombie',phase='zombies',body=[dict(op='zombie_run') for _ in range(steps)]))
        out.append((label+'-'+str(i),c))
    for i in range(112):
        c,ops=setup(i,('普通僵尸','旗帜僵尸','小丑僵尸','雪人僵尸')[i%4])
        v=ops[2]['values'];v.update(血量=(300,0,-1,-90,-298,-799,-999,-1024)[i//4%8],方向=(-1,1)[i//2%2],
            手持='玩偶匣' if i%4==2 else '',防具='路障' if i%3==1 else '',受伤=(0,1,49)[i%3],手持受伤=i%5)
        if i%5==1:v['冰冻']=4.
        if i%5==2:v['灰烬']=(399,419,498,499)[i//5%4]
        if i%7==1:v['狂暴']=0.
        if i%7==2:v['眩晕']=1200.
        if i%7==3:v['出场']=(0,48,49,249,498)[i//7%5]
        if i%7==4:v['旋转']=118.
        run(c,ops,'body-render-and-death',i)
    for i in range(56):
        v={'跳舞':(0,248,499,998)[i%4],'跳舞cd':(2,1,3,2000)[i%4],'灯光':1}
        c,ops=setup(200+i,'舞王僵尸',v);ops[4]['targets']=[0,1]
        ops[3]['values'].update(僵尸='伴舞僵尸',跳舞=1.)
        run(c,ops,'dance-summon-order',i)
    for i in range(84):
        kind=('飞贼僵尸','撑杆跳僵尸','气球僵尸','蹦蹦僵尸','矿工僵尸','潜水僵尸')[i%6]
        vals=[{'绳初位置':[50.,-200.],'出场':(499,500,0)[i//6%3]}, {'撑杆':(98.,99.,198.,199.)[i//6%4]},
              {'手持':'气球','气球':(0.,198.,199.)[i//6%3],'中场':0.},{'手持':'弹跳杆'},
              {'手持':'矿镐','出土':i//6%3==2},{'分兵':0.,'憋气':10299.}][i%6]
        c,ops=setup(300+i,kind,vals)
        if i%6==4:
            ops[1]['rally']=[(5.5 if i//6%2 else 8.5)*48.,432.]
            if i//6%3==2:ops.append(dict(op='plant_original',name='土豆地雷',cell=[8,5]))
        if i%6==5:
            for row in (7,8):ops.append(dict(op='tile_replace',cell=[row,5],value={'方块':'水'}))
        run(c,ops,'native-special-movement',i)
    for i in range(92):
        kind=('投篮车僵尸','雪橇车僵尸')[i%2]
        v=dict(大小=3.,前进=3.,篮球cd=1.,篮球=1.,篮球总量=1.,投篮=(0,118,119,198,199)[i//2%5],撞车=0.,轮子=4.,雪容量=(0,1,4)[i//2%3])
        if v['投篮']>0:v['篮球cd']=220.
        if i%3==1:v['_pvp_card']='zombie:投篮车僵尸'
        if i%5==1:v['_pvp_content']='小鬼炮'
        if i%7==1:v['血量']=0.
        c,ops=setup(420+i,kind,v)
        if i%3==0:ops.append(dict(op='plant_original',name=('地刺','地刺王','豌豆射手','大蒜')[i//3%4],cell=[8,5]))
        if i%4==0:ops.append(dict(op='tile_replace',cell=[9,5],value={'方块':'空'}))
        if i%5==0:ops.append(dict(op='tile_replace',cell=[8,6],value={'方块':'基岩'}))
        run(c,ops,'vehicles-armor-and-ammo',i)
    for i in range(72):
        v=dict(大小=3.,手持='锤子1',手持动画=list(([0,0,0,0,2,1],[0,0,0,0,1,1],[3,4,2,-2,2,2],[0,0,0,0,0,0])[i%4]),
               半血=500.,血量=(1000,100,-678,-1024)[i//4%4],啃咬=(500.,350.,0.)[i%3])
        if i%3==1:v.update(苏醒=(0,7998,7999)[i//3%3],红眼=0.)
        c,ops=setup(600+i,'巨人僵尸',v)
        c['heroes']['plant']['玩家位置']=[290.,380.,0.,0.]
        if i%5==1:ops.append(dict(op='plant_original',name='豌豆射手',cell=[8,5]))
        run(c,ops,'giant-hammer-wake-and-imp',i)
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(motion.__file__),Path(phase.__file__),Path(shared.__file__),
           shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',
           motion.RAW,motion.BITES,motion.BLACK,motion.CACTUS,MINER,shared.BATTLE,motion.CONTENT,shared.SEPTEMBER,shared.PLANT_ZOMBIES,
           phase.PERIODIC,phase.EXPANSION,shared.ROOT/'extract/live/zombie_coordinates.marshal',shared.ROOT/'extract/live/zombie_body_index.marshal']
    sys.exit(shooting.main(paths,reference,cases,ActionExtension,'typed72-mobile-zombie-region'))
