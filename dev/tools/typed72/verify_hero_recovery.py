"""Run the real room-frame water, masochist, sturdy and recovery methods in order."""
import copy
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_resources as res
shared=res.shared
hero=res.hero
shooting=res.shooting
CATALOG64=shared.PVP/'pvp64_catalog.py'


def reference():
    ref=res.reference()
    env=dict(team_of=lambda s:'plant' if s.startswith('plant') else 'zombie')
    for key in ('MASOCHIST_SECRET','MASOCHIST_COOLDOWN','MASOCHIST_EARLY_SUN','MASOCHIST_LATE_SUN','MASOCHIST_EARLY_SECONDS'):
        env[key]=hero.constant(res.seat.CATALOG,key)
    for key in ('STURDY_SECRET','STURDY_COOLDOWN_CUT'):env[key]=hero.constant(CATALOG64,key)
    env['battle']=hero.selected_class(shared.BATTLE,['_deathmatch_water','_masochist','_masochist_seat','_sturdy','_sturdy_seat','_recover_heroes'],'Recovery',env)
    ref['recovery']=env
    return ref


class RecoveryExtension(res.ResourceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.recovery_seen=False
        for name,fn in ref['recovery']['battle'].__dict__.items():
            if callable(fn):setattr(self.b,name,types.MethodType(fn,self.b))
    def operation(self,op):
        b=self.b;name=op['op']
        if name=='recovery_setup':
            self.recovery_seen=True;b.present=frozenset(op['present']);b.deathmatch=op['deathmatch']
            b.rules.update(hero_regen_delay=op['delay'],hero_regen_interval=op['interval'],hero_regen_amount=op['amount'])
            for row,values in zip(b.map['tiles'],op['water']):
                for cell,value in zip(row,values):cell['water']=bool(value)
            for side,values in op['cooldowns'].items():b.players[side]['cooldowns']=dict(values)
        elif name=='recovery_status':b.avatars[op['side']].update(copy.deepcopy(op['fields']))
        elif name=='hero_recover':
            b._deathmatch_water(op['elapsed']);b._masochist();b._sturdy();b._recover_heroes(op['elapsed'])
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if self.recovery_seen:row['cooldowns']={s:p['cooldowns'] for s,p in self.b.players.items()}


def cases():
    src=res.phase.cases()[0][1];out=[]
    for i in range(288):
        c=copy.deepcopy(src);c['seed']=527200+i;ops=c['operations']=c['operations'][:1]
        mode=('duel','duo','coop','pve')[i%4];ops[0]['mode']=mode
        seats={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'coop':['plant','plant2'],'pve':['plant']}[mode]
        present=list(seats)
        if i%12==1:present.remove('plant2')
        water=[[0]*len(row) for row in ops[0]['solid']]
        cols=len(water[0]);width=cols*48.
        # Publish water independently of native terrain, covering all nine
        # deathmatch sampling points and both sides of the periodic seam.
        row=8-(i//3)%3;col=(i//9)%cols;water[row][col]=1
        water[8][0]=1;water[8][-1]=1
        now=(0.,5.,119.999,120.,123.,200.)[i//4%6]
        elapsed=(.004,.04,.9999999995,1.,2.4,10.)[i//24%6]
        cooldowns={s:{'z':now+10.,'a':now+.04,'ready':now,'done':now-1.} for s in c['players']}
        ops += [dict(op='resources_setup',accounts={s:[100.,10.] for s in c['players']}),
                dict(op='recovery_setup',present=present,water=water,cooldowns=cooldowns,deathmatch=i%5!=0,
                     delay=(0.,1.,5.)[i//4%3],interval=(.04,1.,2.5)[i//12%3],amount=(1.,3.,50.)[i//36%3])]
        for n,s in enumerate(c['players']):
            c['players'][s]['secrets']=['secret:抖M','secret:强健'] if (i+n)%3 else []
            hp=(0.,.5,1.,12.,39.,40.)[(i+n)%6]
            p=[(-.1,width+.1,col*48.+(9.5 if i%2 else 38.5),264.)[(i+n)%4],(8.98*48.,-.01,12.*48.,8.2*48.)[i//6%4],0.,0.]
            fields={'玩家血量':hp,'玩家位置':p,'玩家倒地':(0.,1.,89.,90.)[(i+n)%4],
                    '_pvp_previous_hp':hp+(1. if (i+n)%2 else 0.),'_pvp_last_damage':now-(0.,5.,10.)[i//8%3],
                    '_pvp_regen_progress':(0.,.0399999995,.9999999995,2.4)[i//6%4]}
            if i%3:fields['_pvp_water_damage_clock']=(.9999999995,0.,2.5)[i%3]
            if i%4:fields['_pvp_masochist_ready']=now+(-.001,0.,.001)[i//4%3]
            if i%7==0:fields['_pvp_sturdy_down']=True
            ops.append(dict(op='recovery_status',side=s,fields=fields))
            if (i+n)%3==1:ops.append(dict(op='proxy',target=s))
        for j in range(4):
            time=now+j*.04
            ops += [dict(op='clock',tick=round(time*250),time=time),dict(op='hero_recover',elapsed=elapsed)]
            if j==1:ops.append(dict(op='recovery_status',side='plant',fields={'玩家血量':.5,'玩家倒地':0.}))
            if j==2:ops.append(dict(op='recovery_status',side='plant',fields={'玩家倒地':1.}))
        out.append(('room-recovery-order-and-boundaries-'+str(i),c))
    return out


if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(res.__file__),Path(res.hp.__file__),Path(res.phase.__file__),Path(shared.__file__),
           CATALOG64,res.seat.CATALOG,res.seat.SIM,shared.BATTLE,hero.PHYSICS,res.VIEW,
           shared.ROOT/'tools/typed72/resources_probe.cpp',shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    sys.exit(shooting.main(paths,reference,cases,RecoveryExtension,'typed72-native-room-hero-recovery'))
