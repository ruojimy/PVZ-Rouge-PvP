"""Original world regions and PvP72 resource motion, merging and collection."""
import ast
import copy
import marshal
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_hero_phase as seat
hp=seat.hp
phase=hp.phase
shared=hp.shared
shooting=hp.shooting
hero=hp.hero
VIEW=shared.PVP/'world_view.py'

def reference():
    ref=hp.reference()
    env=dict(math=math,DUEL='duel',DUO='duo',team_of=lambda s:'plant' if s.startswith('plant') else 'zombie')
    shooting.projectiles.functions(seat.SIM,['wrap_delta'],env)
    env['MERGED_SUN_GROWTH_CAP']=hero.constant(VIEW,'MERGED_SUN_GROWTH_CAP')
    shooting.projectiles.functions(VIEW,['sun_scale'],env)
    base=hero.selected_class(seat.SIM,['_id','resource','_collect','team_seats'],'ResourceBase',env)
    names={'resource','_collect','drop_coin','_advance_suns','_merge_suns','_shared_collector','_auto_shared_sky'}
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    nodes=[n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(nodes)==len(names)
    cls=ast.ClassDef(name='NativeResources',bases=[ast.Name(id='ResourceBase',ctx=ast.Load())],keywords=[],body=nodes,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(shared.BATTLE),'exec'),env)
    economy,=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_economy']
    settle=economy.body[-1]
    assert isinstance(settle,ast.For) and ast.dump(settle.iter)==ast.dump(ast.parse('list(self.resources.items())',mode='eval').body)
    env['settle']=compile(ast.Module(body=[settle],type_ignores=[]),str(shared.BATTLE),'exec')
    env['regions']={name:marshal.loads((shared.ROOT/('extract/live/'+name+'.marshal')).read_bytes())
                    for name in ('sun_motion','water_animation','important_blocks','water_ice_clock')}
    ref['resources']=env
    return ref

class ResourceExtension(hp.HeroPhysicsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['resources'];self.resource_ref=env
        b=self.b;g=self.g
        self.resource=env['NativeResources']();self.resource.__dict__=b.__dict__
        b.resources={};b._sun_motion={};b.ids=0;b.coins=0.
        b.SUN_MERGE_TILES=.6;b.SUN_MERGE_SPEED=.05;b.width=case['world_rules']['width']
        for p in b.players.values():p['resource']=0.;p['stats']['earned']=0.
        b.audio=types.SimpleNamespace(emit=g['沉浸播音'])
        b.engine.regions.update(env['regions'])
        g.update(水波=0.,shui=0.)
    def operation(self,op):
        name=op['op'];r=self.resource;b=self.b;g=self.g
        if name=='track_setup':
            result=super().operation(op);b.mode=op['mode'];b.team_mode=b.mode in ('duo','coop');return result
        if name=='resources_setup':
            b.ids=op.get('sequence',0);b.coins=op.get('coins',0.);g['水波']=op.get('wave',0.)
            for s,v in op['accounts'].items():
                p=b.players[s];p['resource']=v[0];p['stats']['earned']=v[1]
                if len(v)>2:p['stats']['coins']=v[2]
        elif name=='resource':return r.resource(op['side'],op['amount'],*op['point'],op['source'])
        elif name=='coin':return r.drop_coin(op['amount'],*op['point'],op.get('kind','coin'))
        elif name=='resource_fields':
            for key in ('shared','coin','born'):
                if key in op:b.resources[op['id']][key]=op[key]
            if 'sun' in op:b._sun_motion[op['id']]=copy.deepcopy(op['sun'])
        elif name=='collect':r._collect(op['id'],op.get('seat'))
        elif name=='resource_expire':b.resources.pop(op['id'],None)
        elif name=='resource_remove_motion':b._sun_motion.pop(op['id'],None)
        elif name=='sun_advance':r._advance_suns()
        elif name=='suns_merge':r._merge_suns()
        elif name=='resource_settle':
            b.rules['sun_lifetime']=op['lifetime'];exec(self.resource_ref['settle'],dict(self.resource_ref,self=r))
        elif name=='resource_auto':return r._auto_shared_sky(op['id'])
        elif name=='important':self.important(*op['cell'],op['block'])
        elif name in ('world_water','world_important','world_ice'):
            region={'world_water':'water_animation','world_important':'important_blocks','world_ice':'water_ice_clock'}[name]
            if name=='world_ice':g['冻水']=g.get('_pvp_water_ice',0.)
            b.engine.execute(region)
            if name=='world_ice':g['_pvp_water_ice']=g['冻水']
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row);b=self.b;g=self.g
        row.update(resource_ids=b.ids,coins=b.coins,resources=list(b.resources.values()),sun_motions=list(map(list,b._sun_motion.items())),
                   world_region=[g['水波'],g['shui'],g.get('__native_landing',0)])
        row['resource_accounts']={s:dict(balance=p['resource'],earned=p['stats']['earned'],**({'coins':p['stats']['coins']} if 'coins' in p['stats'] else {}))
                                  for s,p in b.players.items()}

def cases():
    proto=phase.cases()[0][1];out=[]
    def base(i):
        c=copy.deepcopy(proto);c['seed']=720500+i;ops=c['operations']=c['operations'][:1]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops.append(dict(op='resources_setup',accounts={s:[100.,10.] for s in c['players']},wave=(0.,498.,499.,500.)[i%4]))
        return c,ops
    for i in range(96):
        c,ops=base(i)
        for j in range(6):
            side=('plant','plant2','zombie','zombie2')[((i//4)+j)%4]
            p=[(264.,959.8,-.1,960.1)[(i+j)%4],(412.,.1,600.)[i//4%3]]
            ops.append(dict(op='resource',side=side,amount=(15,25,125)[(i+j)%3],point=p,source=('sky','day_income','grave:1')[j%3]))
            if side.startswith('plant'):
                ops.append(dict(op='resource_fields',id='r'+str(j+1),sun=[i,[*p,.4,-.2],0,i%2]))
        if i%3==1:ops.append(dict(op='resource_expire',id='r1'))
        for j in range(4):ops.append(dict(op='sun_advance'))
        out.append(('native-sun-motion-and-orphans-'+str(i),c))
    for i in range(96):
        c,ops=base(200+i)
        c['world_rules']['width']=(960.,48.,24.)[i%3]
        for j in range(7):
            side='plant2' if j==4 and i%2 else 'plant'
            p=[(6.,32.,34.,48.,7.,952.,961.)[j],400.+(29. if j==2 and i%2 else 0.)]
            ops.append(dict(op='resource',side=side,amount=(15,25,50,250)[(i+j)%4],point=p,source='native_producer'))
            ops.append(dict(op='resource_fields',id='r'+str(j+1),born=float(j),shared=j%2==0 if i%4 else False,
                            sun=[3,[*p,.05 if (i+j)%3 else 0.,.02 if i%5 else 0.],8,1]))
            if j==2 and i%5:ops[-1]['coin']='coin'
        ops+=[dict(op='suns_merge'),dict(op='suns_merge'),dict(op='sun_advance'),dict(op='suns_merge')]
        out.append(('sun-merge-order-and-compatibility-'+str(i),c))
    for i in range(112):
        c,ops=base(400+i)
        for s in c['players']:
            c['players'][s]['hp']=0. if (i//4)%3==0 and s.startswith('plant') else 40.
            if (s=='plant' and i%2) or (s=='plant2' and i%3==2):c['players'][s]['secrets']=['secret:阳光']
        for j in range(4):
            p=[40.+j*200.,350.]
            ops.append(dict(op='resource',side='plant' if j%2==0 else 'plant2',amount=(15.,25.,160.)[(i+j)%3],point=p,source='sky' if j%2 else 'native_producer'))
            if j==1:ops.append(dict(op='resource_fields',id='r2',shared=True))
        ops.append(dict(op='coin',amount=50.,point=[40.,350.],kind='moneybag' if i%2 else 'coin'))
        ops+=[dict(op='clock',tick=250,time=(15.,30.,31.)[i//4%3]),dict(op='resource_settle',lifetime=30.),
              dict(op='resource_settle',lifetime=30.),dict(op='collect',id='r1',seat='plant2'),dict(op='sun_advance')]
        out.append(('collection-coins-and-shared-sky-'+str(i),c))
    for i in range(80):
        c,ops=base(600+i)
        c['globals']['冻水']=(0.,1.,2.5)[i%3]
        for j in range(3):
            row,col=7,3+j*2;block='坟墓' if j%2==0 else '雪'
            value={'方块':block}
            if block=='坟墓':value['长出']=(48,49,198,199)[i%4]
            elif i%4:value['雪消失']=(9998,9999,0)[i%3]
            ops += [dict(op='tile_replace',cell=[row,col],value=value),dict(op='important',cell=[row,col],block=block)]
        for j in range(3):ops += [dict(op='world_water'),dict(op='world_important'),dict(op='world_ice')]
        out.append(('water-graves-snow-and-important-order-'+str(i),c))
    return out

if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(hp.__file__),Path(phase.__file__),Path(shared.__file__),shared.BATTLE,seat.SIM,hero.PHYSICS,VIEW,
           shared.ROOT/'tools/typed72/resources_probe.cpp',shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    paths += [shared.ROOT/('extract/live/'+s+'.marshal') for s in ('sun_motion','water_animation','important_blocks','water_ice_clock')]
    sys.exit(shooting.main(paths,reference,cases,ResourceExtension,'typed72-native-world-resources'))
