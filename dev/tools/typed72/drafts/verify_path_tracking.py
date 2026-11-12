"""Persistent native player/plant path fields after placement and terrain edits."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_resources as res
shared=res.shared
hero=res.hero
shooting=res.shooting
phase=res.phase

def reference():return res.reference()
class PathExtension(res.ResourceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.path_seen=False
    def operation(self,op):
        name=op['op'];g=self.g
        if name=='path_setup':
            self.path_seen=True
            g.update(输出植物=list(op['targets']),产光植物=list(op['producers']),
                     先别追植=op['hold'],paoku=op['running'],输出植物数=op['output'])
            self.physics.initialize_tracking({'玩家位置':list(op['point'])+[0.,0.]})
        elif name=='path_step':
            self.physics.update_tracking({'玩家位置':list(op['point'])+[0.,0.]},'我是僵尸' if op['follow'] else '正常模式')
        elif name=='path_goal':g['目标位置']=list(op['cell'])
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if self.path_seen:
            g=self.g
            row['paths']=dict(fields=[[g[p+'洪水cd'],g[p+'洪水覆盖'],g[p+'洪水'],g[p+'洪水圈']] for p in ('人','植')],
                              target=g['目标植物'],goal=g['目标位置'],hold=g['先别追植'],running=g['paoku'],output=g['输出植物数'])

def cases():
    prototype=phase.cases()[0][1];out=[]
    for i in range(144):
        c=copy.deepcopy(prototype);c['seed']=543720+i;ops=c['operations']=c['operations'][:1]
        cols=len(c['plant_world']['grid'][0]);tile=c['plant_world'].get('tile',48.);width=cols*tile
        ops.append(dict(op='resources_setup',accounts={s:[0.,0.] for s in c['players']}))
        ops.append(dict(op='path_setup',point=[264.,412.8],targets=['向日葵','豌豆射手','坚果'],producers=['向日葵'],
                        hold=(0.,1.,300.)[i%3],output=i%8,running=3.))
        for j in range(i%7):
            name=('向日葵','豌豆射手','坚果')[j%3]
            ops.append(dict(op='plant_original',name=name,cell=[8,(j*3+2)%cols]))
            if j==1 and i%2:ops.append(dict(op='plant_write',plant=j,values={'睡觉':0.}))
            if j==3 and i%3:ops.append(dict(op='tile_replace',cell=[7,(j*3+2)%cols],value={'方块':'石'}))
        if i%4==0:ops.append(dict(op='path_goal',cell=[8,-1]))
        for j in range(10):
            point=[(-.1,width+.1,264.,width*2.-24.)[(i+j)%4],(-50.,412.8,1000.)[(i//4+j)%3]]
            ops.append(dict(op='path_step',point=point,follow=(i+j)%3==0))
            if j in (2,6):ops.append(dict(op='tile_replace',cell=[7,0],value={'方块':'空' if j==6 else '石'}))
        out.append(('tracking-queues-targets-and-map-edits-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(res.__file__),Path(res.hp.__file__),Path(phase.__file__),Path(shared.__file__),
           shared.ROOT/'tools/typed72/resources_probe.cpp',shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',
           hero.PHYSICS,shared.PVP/'native_flood.py',shared.PVP/'native_geometry.py',shared.BATTLE]
    paths += [shared.ROOT/('extract/live/physics_'+n+'.marshal') for n in ('tracking_initialize','tracking_bind','tracking_coordinates','tracking_player','tracking_targets','tracking_plants')]
    sys.exit(shooting.main(paths,reference,cases,PathExtension,'typed72-native-path-tracking'))
