"""Drive the two real per-seat loops from PvP72 NativeBattle._step_original."""
import ast
import copy
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_hero_physics as hp
phase=hp.phase
shared=hp.shared
shooting=hp.shooting
hero=hp.hero
BALANCE=shared.LOCAL/'balance.py'
CATALOG=shared.LOCAL/'pvp58_catalog.py'
SIM=shooting.projectiles.SIMULATION

def reference():
    ref=hp.reference()
    env=dict(DUEL='duel',DUO='duo',team_of=lambda s:'plant' if s.startswith('plant') else 'zombie')
    shooting.projectiles.functions(SIM,['wrap_delta'],env)
    for key in ('MASOCHIST_SECRET','MASOCHIST_RISE_FRAMES','NATIVE_RISE_FRAMES'):env[key]=hero.constant(CATALOG,key)
    for key in ('STURDY_GRAVE','STURDY_GRAVE_HERO_HP','STURDY_GRAVE_BALLOON_HP','NATIVE_BALLOON_HP'):env[key]=hero.constant(BALANCE,key)
    shooting.projectiles.functions(BALANCE,['hero_hp','balloon_hp'],env)
    shooting.projectiles.functions(shared.BATTLE,['_native_match_secrets'],env)
    env['navigation']=hero.selected_class(shared.BATTLE,['_float_body','_rally_rise','_jump_cap'],'Navigation',env)
    env['rally']=hero.selected_class(SIM,['command_seat','rally_for','set_rally'],'Rally',env)
    env['jump_cap']=hero.selected_class(hero.ZSECRETS,['jump_cap'],'ZombieJump',env).jump_cap
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    fn,=[f for f in ast.walk(tree) if isinstance(f,ast.FunctionDef) and f.name=='_step_original']
    seat_loops=[n for n in fn.body if isinstance(n,ast.For) and ast.dump(n.iter)==ast.dump(ast.parse('self.avatars.items()',mode='eval').body)]
    for label,term in [('advance','_jump_presses'),('effects','advance_hero_effects')]:
        loop,=[n for n in seat_loops if any(getattr(x,'attr',None)==term for x in ast.walk(n))]
        env[label]=compile(ast.Module(body=[loop],type_ignores=[]),str(shared.BATTLE),'exec')
    init,=[n for n in ast.walk(tree) if isinstance(n,ast.For) and
           any(getattr(x,'attr',None)=='make_state' for x in ast.walk(n))]
    env['initialize']=compile(ast.Module(body=init.body,type_ignores=[]),str(shared.BATTLE),'exec')
    ref['seat_phase']=env
    return ref

class HeroPhaseExtension(hp.HeroPhysicsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.seat_ref=ref['seat_phase'];b=self.b;env=self.seat_ref
        for name in ('_float_body','_rally_rise','_jump_cap'):setattr(b,name,types.MethodType(getattr(env['navigation'],name),b))
        b.command_seat=env['rally'].command_seat
        for name in ('rally_for','set_rally'):setattr(b,name,types.MethodType(getattr(env['rally'],name),b))
        b.zsecrets.jump_cap=types.MethodType(env['jump_cap'],b.zsecrets)
        b.SECRET_TRIPLE_JUMP='secret:疾行';b.TRIPLE_JUMP_CAP=3
        b.engine.physics=self.physics;b.rally_points={};b.rally_point=None;self.control_seen=False
    def operation(self,op):
        name=op['op'];b=self.b;env=self.seat_ref
        if name=='track_setup':
            result=super().operation(op)
            b.mode=op['mode'];b.team_mode=b.mode in ('coop','duo');b.present=frozenset(b.seats)
            return result
        if name=='hero_phase_setup':
            self.control_seen=True;b._jump_presses={}
            for row,values in zip(b.map['tiles'],op['water']):
                for cell,v in zip(row,values):cell['water']=bool(v)
            for side,values in op['seats'].items():
                p=b.players[side];p.update(deck=list(values['deck']),x=values['point'][0],y=values['point'][1],
                         input={'move':values['move']},jump_held=values['held'])
                env['native_secret_names']=lambda unused:list(values['native_secrets'])
                b.rules['hero_hp']=values['hp'];b._jump_presses[side]=values['presses']
                exec(env['initialize'],dict(env,self=b,side=side,player=p));b.hero_states[side]=b.avatars[side]
        elif name=='hero_phase_status':
            avatar=b.avatars[op['side']];avatar.update(copy.deepcopy(op['fields']))
            if 'launch' in op:avatar['_pvp_launch_attack']=hero.decode_attack(op['launch'])
        elif name=='hero_flag':
            b.set_rally(op['side'],{'x':480.,'y':240.} if op['on'] else None)
        elif name=='hero_phase_step':
            exec(env['advance'],dict(env,self=b))
        elif name=='hero_phase_effects':
            b.rules['tail_activation_seconds']=op['tail_at']
            exec(env['effects'],dict(env,self=b,now=op['now']))
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if self.control_seen:row['hero_controls']={s:[self.b._jump_presses[s],self.b.players[s]['max_hp']] for s in self.b.seats}

def cases():
    src=phase.cases()[0][1];out=[]
    for i in range(160):
        c=copy.deepcopy(src);c['seed']=847200+i;ops=c['operations']=c['operations'][:9]
        mode=('duel','duo','pve','coop')[i%4];ops[0]['mode']=mode
        present={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'coop':['plant','plant2'],'pve':['plant']}[mode]
        # Supply published positions separately from the live native terrain.
        cfg={};water=[[0]*len(row) for row in ops[0]['solid']]
        for n,s in enumerate(present):
            deck=(['zombie:坚固脑光墓碑'] if (i+n)%3 else [])+(['zsecret:石更！'] if i%2 else [])
            secrets=(['secret:疾行','secret:抖M'] if s.startswith('plant') else
                     [k for j,k in enumerate(('zsecret:豌豆','zsecret:威压')) if ((i//4+n)>>j)&1])
            c['players'][s]['secrets']=secrets
            col=2+n*3;cfg[s]=dict(point=[(col+.5)*48.,8.6*48.],hp=40.,native_secrets=['硬化','猫尾'],deck=deck,
                                      move=-1 if n%2 else 1,held=i%2==0,presses=i//4%4)
            for r in (7,8) if i%3 else (8,):water[r][col]=int(i%5!=0)
        ops.append(dict(op='hero_phase_setup',seats=cfg,water=water))
        ops.append(dict(op='roster_replace',targets=[0,1,2,3]+list(present)))
        for n,s in enumerate(present):
            if s.startswith('zombie'):ops.append(dict(op='hero_flag',side=s,on=True))
            fields={'辣飞天':16 if (i+n)%4!=0 else 0,'__pvz_sb_chili_launch_lock_until':4.125,
                    '猫尾':48,'猫尾cd':149,'冻水':7,'_pvp_cold_until':34,'_pvp_ice':(0,1,1000,1001)[(i+n)%4],
                    '_pvp_stun':(0,2)[i%2],'_pvp_butter':(0,1,2)[i%3]}
            ops.append(dict(op='hero_phase_status',side=s,fields=fields,launch=({'tuple':[s,i]},None,[],False)[(i+n)%4]))
        ops.append(dict(op='hero_phase_step'))
        for n,s in enumerate(present):
            fields={'玩家倒地':(0,1,85,90)[i//4%4],'玩家恢复':(749,999,1000,1999,2000)[i//4%5],
                    '玩家血量':(0,1,12,40)[(i//4+n)%4]}
            ops.append(dict(op='hero_phase_status',side=s,fields=fields))
            if s.startswith('zombie') and i%3:ops.append(dict(op='hero_flag',side=s,on=False))
        for j in range(3):
            ops+=[dict(op='hero_phase_step'),dict(op='hero_phase_effects',now=(i+j)%4*.25,tail_at=.5)]
        out.append(('native-seat-loop-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(hp.__file__),Path(phase.__file__),Path(shared.__file__),shared.ROOT/'tools/typed72/world_rules_probe.cpp',
           shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',shared.ROOT/'src/core/number_text.h',shared.BATTLE,hero.PHYSICS,phase.PERIODIC,
           phase.EXPANSION,shared.PVP/'native_bytecode.py',BALANCE,CATALOG,SIM,shared.ROOT/'src/sim/pvp/gen/pm_native_battle.cpp']
    sys.exit(shooting.main(paths,reference,cases,HeroPhaseExtension,'typed72-native-hero-seat-loops'))
