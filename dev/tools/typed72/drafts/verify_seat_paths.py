"""Persistent seat/rally fields and native dictionary alias/save boundaries."""
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_path_tracking as paths
res=paths.res
shared=paths.shared
hero=paths.hero
shooting=paths.shooting
phase=paths.phase


def reference():
    ref=paths.reference()
    env=dict(math=math,copy=copy,DUO='duo',__package__=shared.PACKAGE,
             team_of=lambda s:'plant' if s.startswith('plant') else 'zombie')
    names=['_team_tracking','_switch_tracking','rally_destination','_update_rally_tracking',
           '_restore_rally_tracking','_rally_zombie_gate','rally_tracking_for']
    env['battle']=hero.selected_class(shared.BATTLE,names,'PathBanks',env)
    env['commands']=hero.selected_class(res.seat.SIM,['command_seat','command_for','rally_for','set_rally'],'Commands',env)
    ref['path_banks']=env
    return ref


class SeatPathExtension(paths.PathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;env=ref['path_banks'];self.bank_seen=False;self.baseline=None
        for name,method in env['battle'].__dict__.items():
            if callable(method):setattr(b,name,types.MethodType(method,b))
        b.command_seat=env['commands'].command_seat
        for name in ('command_for','rally_for','set_rally'):
            setattr(b,name,types.MethodType(getattr(env['commands'],name),b))
        b.engine.physics=self.physics;b._seat_tracking={};b._rally_trackings={}
        b._rally_tracking=None;b._rally_tracking_base=None;b.rally_points={};b.rally_point=None
        b._native_zombie_gate=lambda:None
        self.keys=sys.modules[shared.PACKAGE+'.native_physics'].TRACKING_KEYS
    def operation(self,op):
        name=op['op'];b=self.b;g=self.g
        if name=='banks_setup':
            self.bank_seen=True;b.command=op['command'];b.commands=dict(op['commands'])
            b.scripted=op['scripted'];b.present=frozenset(b.seats);b.terrain_revision=op['revision']
            b.map['cols']=len(b.map['tiles'][0])
            for seat,state in b.hero_states.items():state['_pvp_seat']=seat
        elif name=='banks_command':
            b.command=op['command'];b.commands.update(op['commands'])
        elif name=='banks_flag':b.set_rally(op['side'],dict(x=op['point'][0],y=op['point'][1]) if op['point'] is not None else None)
        elif name=='banks_team':return b._team_tracking()
        elif name=='banks_rallies':b._update_rally_tracking(b.avatars['zombie'])
        elif name=='banks_destination':return b.rally_destination(op['side'])
        elif name=='banks_publish':
            for y,x,value in op['changes']:b.map['tiles'][y][x]['solid']=bool(value)
            b.terrain_revision=op['revision']
        elif name=='banks_public_hp':b.players[op['side']]['hp']=op['value']
        elif name=='banks_begin':
            self.baseline={key:g[key] for key in self.keys if key in g}
            b._switch_state=dict(entry='plant',track=None)
        elif name=='banks_end':
            g.update(self.baseline);self.baseline=None;b._switch_state=None
        elif name=='banks_alias':b._set_alias(op['side'])
        elif name=='banks_switch':b._switch_tracking(self.units[op['unit']])
        elif name=='banks_rally':
            g['l']=next(i for i,z in enumerate(g['僵尸']) if z is self.units[op['unit']]);b._rally_zombie_gate()
        elif name=='banks_restore':b._restore_rally_tracking()
        elif name=='banks_native_write':
            # Writes performed by the original mobile region after its gate.
            # Matrix contents mutate in place; counters replace scalar values.
            g['先别追植']=op['hold'];g['paoku']=op['running'];g['目标植物']=op['target']
            g['人洪水cd']=op['cooldown']
            y,x,v=op['cell'];g['洪水'][op['field']][y][x]=v
        elif name=='banks_unit':
            z=self.units[op['unit']]
            if op['seat'] is None:z.pop('_pvp_seat',None)
            else:z['_pvp_seat']=op['seat']
            if op['charm']:z['魅惑']=0.
            else:z.pop('魅惑',None)
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if not self.bank_seen:return
        b=self.b;g=self.g;identities={}
        def identity(value):
            key=id(value)
            if key not in identities:identities[key]=len(identities)
            return identities[key]
        def chase(state):
            return dict(fields=state['洪水'],goal=state['目标位置'],target=state['目标植物'],
                        running=state['paoku'],output=state['输出植物数'],aliases=[identity(x) for x in state['洪水']])
        def snapshot(state):
            if state is None:return None
            return dict(fields=[[state[p+'洪水cd'],state[p+'洪水覆盖'],state[p+'洪水'],state[p+'洪水圈']] for p in ('人','植')],
                        chase=chase(state),hold=state['先别追植'],hero=[state['wjy'],state['wjx']],
                        aliases=[identity(state[p+suffix]) for p in ('人','植') for suffix in ('洪水','洪水圈')])
        def rally(state,goal=None):
            return dict(path=snapshot(state),goal=state.get('_pvp_goal',goal)) if state is not None else None
        seats=('plant','zombie','plant2','zombie2')
        row['path_banks']=dict(current=snapshot(g),seats={s:snapshot(b._seat_tracking[s]) for s in seats if s in b._seat_tracking},
            rallies={s:rally(b._rally_trackings[s]) for s in seats if s in b._rally_trackings},
            shared=rally(b._rally_tracking,getattr(b,'_rally_tracking_goal',None)),
            base=chase(b._rally_tracking_base) if b._rally_tracking_base else None,
            phase=snapshot(self.baseline),selected=b._switch_state['track'] if b._switch_state else None)


def cases():
    out=[]
    for i in range(96):
        c=copy.deepcopy(phase.cases()[0][1]);c['seed']=972000+i
        ops=c['operations']=c['operations'][:1];mode=('duel','duo','coop','pve')[i%4];ops[0]['mode']=mode
        present={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'coop':['plant','plant2'],'pve':['plant']}[mode]
        ops.append(dict(op='path_setup',point=[264.,412.8],targets=['向日葵','豌豆射手'],producers=['向日葵'],hold=7.,output=1.,running=2.))
        ops.append(dict(op='banks_setup',command='attack' if mode in ('coop','pve') or i%8<4 else 'follow',
                        commands=dict(zombie='follow',zombie2='attack'),scripted=mode in ('coop','pve'),revision=0))
        for n,seat in enumerate(('plant','zombie','plant2','zombie2')):
            ops.append(dict(op='write',target=seat,values={'玩家位置':[120.+n*192.,412.8,0.,0.]}))
        for j in range(i%3):ops.append(dict(op='plant_original',name='向日葵' if j else '豌豆射手',cell=[8,3+j*5]))
        ops.extend([dict(op='banks_team'),dict(op='banks_team')])
        for seat,point in [('zombie',[1.,380.]),('zombie2',[959.,380.])]:
            ops.append(dict(op='banks_flag',side=seat,point=point))
        ops.append(dict(op='banks_rallies'))
        for j in range(4):
            ops.append(dict(op='banks_unit',unit=j,seat=('zombie','zombie2',None,'plant2')[j],charm=j==3 and i%3==0))
        ops.append(dict(op='banks_begin'))
        for j in (0,1,2,3,1,0):
            ops.append(dict(op='banks_alias',side='plant2' if 'plant2' in present and j%2 else 'plant'))
            ops.append(dict(op='banks_switch',unit=j))
            ops.append(dict(op='banks_rally',unit=j))
            ops.append(dict(op='banks_native_write',hold=13.+j,running=4.+j,target=j,cooldown=j,
                            field=j%2,cell=[7,2+j,-4+j]))
        ops.extend([dict(op='banks_end'),dict(op='banks_team'),dict(op='banks_rallies')])
        ops.append(dict(op='banks_flag',side='zombie',point=[480.,300.] if i%2 else None))
        ops.append(dict(op='banks_destination',side='zombie'))
        ops.append(dict(op='banks_publish',changes=[[6,10,1],[7,10,1],[6,9,1]],revision=0))
        ops.append(dict(op='banks_destination',side='zombie'))
        ops.append(dict(op='banks_publish',changes=[],revision=1))
        ops.extend([dict(op='banks_rallies'),dict(op='banks_destination',side='zombie2')])
        ops.append(dict(op='banks_public_hp',side='plant',value=0.))
        if i%3==0:ops.append(dict(op='banks_public_hp',side='plant2',value=0.))
        ops.append(dict(op='banks_command',command='attack',commands=dict(zombie='attack',zombie2='follow')))
        ops.extend([dict(op='banks_team'),dict(op='banks_team'),dict(op='banks_rallies')])
        ops.extend([dict(op='banks_public_hp',side='plant',value=40.),dict(op='banks_team')])
        out.append(('seat-and-rally-persistent-fields-'+str(i),c))
    return out


if __name__=='__main__':
    pinned=[Path(__file__).resolve(),Path(paths.__file__),Path(res.__file__),Path(res.hp.__file__),Path(phase.__file__),
            Path(shared.__file__),shared.BATTLE,res.seat.SIM,hero.PHYSICS,shared.PVP/'native_flood.py',
            shared.ROOT/'tools/typed72/seat_paths_probe.cpp',shared.ROOT/'tools/typed72/resources_probe.cpp',
            shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    pinned += [shared.ROOT/('extract/live/physics_'+n+'.marshal') for n in ('tracking_initialize','tracking_bind','tracking_coordinates','tracking_player','tracking_targets','tracking_plants')]
    sys.exit(shooting.main(pinned,reference,cases,SeatPathExtension,'typed72-seat-and-rally-paths'))
