"""PvP64 zombie controllers with actual summon admission and retained source state."""
import ast
import contextlib
import copy
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_grenadiers as grenades
import verify_scripted_spawn as budget_module
import verify_content_queries as queries
shared=grenades.shared
hero=grenades.hero
shooting=grenades.shooting
SOURCE=grenades.SOURCE
FIELDS=('_pvp_content','_pvp_max_hp','_pvp_base_speed','__pvz_sb_zombie_observed_max_hp',
        '_pvp_throw_clock','_pvp_grab','_pvp_grabbed_by','_pvp_thrown_by','_pvp_split','_pvp_slime_sticky',
        '_pvp_zs_hand_kind','_pvp_flight','_pvp_taunted_by','_pvp_id','_pvp_seat','_pvp_wave_index')


def reference():
    ref=grenades.reference();env=ref['mortar_plants'];env['__package__']=shared.PACKAGE
    for key in ('REDEYE_THROW_SECONDS','REDEYE_THROW_RADIUS'):
        env[key]=hero.constant(grenades.CATALOG,key)
    for path,names in ((grenades.CATALOG,('SLIME_NEXT',)),(SOURCE,('DRAWN_ZOMBIES','ART_SUFFIXES','BELT_STRIDE','GRAB_TICKS'))):
        nodes=[node for node in ast.parse(path.read_text(encoding='utf8')).body if isinstance(node,ast.Assign)
               and any(isinstance(target,ast.Name) and target.id in names for target in node.targets)]
        assert len(nodes)==len(names)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
    shooting.projectiles.functions(shared.PVP/'zombie_secrets.py',['hand_kind'],env)
    hero.selected_class(SOURCE,['configure','zombie_gate','on_belt','finish_zombie','throwable','redeye_step','landed',
        'split','_launch_slime_child','_deferred_slime_child'],'Zombies64',env)
    tag,=[node for node in ast.walk(ast.parse(SOURCE.read_text(encoding='utf8'))) if isinstance(node,ast.FunctionDef) and node.name=='tag_belt']
    env['tag_install']=compile(ast.Module(body=[tag],type_ignores=[]),str(SOURCE),'exec')
    ref['scripted_budget']=budget_module.reference()['scripted_budget']
    ref['content_queries']=queries.reference()['content_queries']
    return ref


class ContentZombie64Extension(grenades.GrenadierExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        r=self.zombies64=ref['mortar_plants']['Zombies64']();r.c=self.content;r.b=self.b;r.g=self.g
        r.belt_keys=set();r.grenadier_step=self.grenadiers.grenadier_step
        t=self.taunt=ref['content_queries']['Taunts']();t.b=self.b;t.g=self.g
        t.sweet_radius=6.;t.potatoes_dirty=True;t.potato_list=[];t.potato_points=[]
        t.taunt_fields={};t.taunt_baseline=None;t.saved_tracking=None;t.hidden_cells=[]
        r.apply_taunt=t.apply_taunt
        self.seen64=False;self.events64=[];self.aliases64=[];self.draws64=[];self.spawn_calls64=[]
        self.spawn_mode64='ok';self.spawned64=0;self.sync64=0
        b=self.b;g=self.g;b._ban_free_spawn_count=0;b.targets=self.c;b._native_objects={}
        b.rules={};b.director=types.SimpleNamespace();b.mode='duel'
        self.budget=b.scripted_spawn_budget=ref['scripted_budget']['ScriptedSpawnBudget'](b)
        original=b._emit
        def emit(name,**payload):
            if name in ('belt_placed','redeye_grab','redeye_throw','slime_split','scripted_summon_deferred'):
                self.events64.append([name,payload]);self.before('zombie64_event');self.after('zombie64_event')
            else:original(name,**payload)
        b._emit=emit
        def alias(first,second):
            self.aliases64.append([first,second]);self.before('zombie64_alias');self.after('zombie64_alias')
        b.expansion.alias_art=alias
        def draw(unit):
            self.draws64.append(self.label(unit));self.before('zombie64_draw');self.after('zombie64_draw')
        r.draw_zombie=draw
        def sync():
            self.sync64+=1
            r.belt_keys={row*65536+col for row,line in enumerate(g['ditu']) for col,cell in enumerate(line)
                         if cell.get('_pvp_belt') and cell.get('方块')=='梯子块'}
            self.before('zombie64_sync');self.after('zombie64_sync')
        b._sync_terrain=sync
        local=dict(ref['mortar_plants'],self=r,b=b,g=g,particles=g['增粒子'])
        exec(ref['mortar_plants']['tag_install'],local);g['增粒子']=local['tag_belt']
        @contextlib.contextmanager
        def exemption():
            b._ban_free_spawn_count+=1
            try:yield
            finally:b._ban_free_spawn_count-=1
        b._ban_free_spawn=exemption
        def spawn(card,owner,x,y,direction,free,parent):
            self.spawn_calls64.append([card,owner,x,y,direction,free,copy.deepcopy(parent),b._ban_free_spawn_count,
                self.c.active['owner'] if self.c.active else None,self.c.active['phase'] if self.c.active else None])
            self.before('zombie64_spawn')
            if self.spawn_mode64=='none':return None
            if self.spawn_mode64=='throw_before':raise RuntimeError('slime constructor before')
            g['新增僵尸']('普通僵尸',[x,y,0.,0.],direction)
            unit=g['僵尸'][-1];self.spawned64+=1;uid='slime:'+str(self.spawned64)
            unit['_pvp_id']=uid;b._native_objects[uid]=unit
            if self.spawn_mode64=='throw_after':raise RuntimeError('slime constructor after')
            self.after('zombie64_spawn')
            return {'id':uid}
        b.spawn=spawn

    def operation(self,op):
        name=op['op'];r=self.zombies64
        if name=='zombie64_setup':
            self.seen64=True;self.b.mode=op['mode'];self.budget.enabled=op['mode'] in ('pve','coop')
            for seat,player in self.b.players.items():player['secrets']=list(op.get('secrets',{}).get(seat,[]))
        elif name=='zombie64_fields':
            unit=self.units[op['unit']];unit.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):unit.pop(key,None)
        elif name=='zombie64_registry':
            if 'unit' in op:self.b._native_objects[op['id']]=self.units[op['unit']]
            else:self.b._native_objects.pop(op['id'],None)
        elif name=='zombie64_belts':r.belt_keys=set(op['keys'])
        elif name=='zombie64_limit':self.b.director.max_zombies=op['value']
        elif name=='zombie64_spawn_mode':self.spawn_mode64=op['value']
        elif name=='zombie64_restore_taunt':self.taunt.restore_taunt()
        elif name in ('zombie64_configure','zombie64_gate','zombie64_finish','zombie64_on_belt','zombie64_throwable',
                      'zombie64_redeye','zombie64_landed','zombie64_split','zombie64_drain','zombie64_tag'):
            try:
                unit=self.units[op['unit']] if 'unit' in op else None
                if name=='zombie64_configure':
                    self.ns['__pvz_sb_K_ZOMBIE_OBSERVED_MAX_HP']='__pvz_sb_zombie_observed_max_hp' if op['observed'] else None
                    return r.configure(unit,dict(content=op['name'],hp=op['hp']))
                if name=='zombie64_gate':r.zombie_gate(unit)
                elif name=='zombie64_finish':r.finish_zombie(unit,op['alive'])
                elif name=='zombie64_on_belt':return r.on_belt(unit)
                elif name=='zombie64_throwable':return self.content_label(r.throwable(unit))
                elif name=='zombie64_redeye':r.redeye_step(unit)
                elif name=='zombie64_landed':r.landed()
                elif name=='zombie64_split':r.split(unit)
                elif name=='zombie64_drain':self.budget.drain()
                elif name=='zombie64_tag':self.g['增粒子'](op['name'],op['point'],6)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.seen64:return
        r=self.budget
        row['zombies64']=dict(events=self.events64,aliases=self.aliases64,draws=self.draws64,spawn=self.spawn_calls64,
            sync=self.sync64,belts=sorted(self.zombies64.belt_keys),exempt=self.b._ban_free_spawn_count,
            units=[{key:unit[key] for key in FIELDS if key in unit} for unit in self.units],
            tiles=[[y,x,cell['_pvp_belt']] for y,line in enumerate(self.g['ditu']) for x,cell in enumerate(line) if '_pvp_belt' in cell],
            budget=dict(enabled=r.enabled,draining=r.draining,count=r.count(),available=r.available(),limit=r.limit,
                deferred=r.deferred,admitted=r.admitted,peak=r.peak_pending,
                pending=[[list(key),item['wave']] for key,item in r.pending.items()]))


def paths():
    return grenades.paths()+[Path(__file__).resolve(),Path(grenades.__file__),Path(budget_module.__file__),
        Path(queries.__file__),budget_module.SOURCE,shared.PVP/'zombie_secrets.py',
        shared.ROOT/'tools/typed72/content_zombies64_probe.cpp']


def cases():
    output=[];prototype=grenades.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1071000+i
        ops=case['operations']=case['operations'][:-3]
        mode=('duel','duo','pve','coop')[i%4]
        ops[0]['mode']=mode
        ops.append(dict(op='zombie64_setup',mode=mode,secrets={s:['zsecret:黏糊糊'] if i%3 else [] for s in ('plant','plant2','zombie','zombie2')}))
        for unit in range(4):
            ops.append(dict(op='zombie64_fields',unit=unit,fields={'位置':[264.+unit*24.,432.,0.,0.],
                '血量':100.,'_pvp_owner':'zombie','_pvp_id':'body-'+str(unit)},erase=['魅惑','灰烬']))
            ops.append(dict(op='zombie64_registry',unit=unit,id='body-'+str(unit)))
        return case,ops
    for i in range(48):
        case,ops=setup(i)
        name=('红眼巨人','史莱姆僵尸','中型史莱姆','小型史莱姆','传送带僵尸','掷弹兵僵尸','普通僵尸','')[i%8]
        ops.append(dict(op='zombie64_configure',unit=0,name=name,hp=(100.,500.,2000.)[i//8%3],observed=bool(i%2)))
        ops.extend([dict(op='zombie64_gate',unit=0),dict(op='zombie64_finish',unit=0,alive=True)])
        output.append(('zombie64-configure-secrets-and-native-aliases-'+str(i),case))
    for i in range(64):
        case,ops=setup(100+i)
        ops.append(dict(op='zombie64_fields',unit=0,fields={'_pvp_content':('红眼巨人','史莱姆僵尸','传送带僵尸','掷弹兵僵尸')[i%4],
            '手持':'梯子','_pvp_zs_hand_kind':'传送带','黄油':1.,'冰冻':1001.,'眩晕':1.,'位置':[(-24.,264.,960.,1920.)[i//4%4],432.,0.,(-2.,-2.8,-3.,-3.3)[i//16]],
            '_pvp_grenade':'wind','_pvp_grenade_clock':10.}))
        column=(-1,5,20,40)[i//4%4]%20;row=(9,8,7,6)[i//16]
        ops.extend([dict(op='tile_replace',cell=[row,column],value={'方块':'梯子块','_pvp_belt':i%3!=0}),
                    dict(op='zombie64_belts',keys=[row*65536+column]),dict(op='zombie64_on_belt',unit=0),
                    dict(op='zombie64_gate',unit=0),dict(op='zombie64_finish',unit=0,alive=i%5!=0)])
        output.append(('zombie64-belt-control-height-wrap-and-climb-'+str(i),case))
    for i in range(48):
        case,ops=setup(200+i)
        for unit in range(1,4):
            ops.append(dict(op='zombie64_fields',unit=unit,fields={'位置':[264.+(-144.,144.,144.0000001)[unit-1],432.,0.,0.],
                '_pvp_id':('z','a','x')[unit-1]}))
        fields=({'_pvp_content':'乌鸦'},{'_pvp_flight':True},{'大小':2.00001},{'大小':None},
                {'_pvp_grabbed_by':'held'},{'_pvp_thrown_by':'thrown'},{'_pvp_grave':True},{'_pvp_orphan_barrel':True},
                {'血量':0.},{'灰烬':0.},{'_pvp_owner':'plant'},{'_pvp_id':None})[i%12]
        ops.append(dict(op='zombie64_fields',unit=1,fields=fields))
        ops.append(dict(op='zombie64_throwable',unit=0,catch=True))
        output.append(('zombie64-grab-candidates-radius-and-id-order-'+str(i),case))
    for i in range(64):
        case,ops=setup(300+i)
        ops.extend([dict(op='zombie64_configure',unit=0,name='红眼巨人',hp=2000.,observed=True),
            dict(op='zombie64_fields',unit=0,fields={'_pvp_throw_clock':(999.,1000.,1999.,2000.)[i%4],
                '血量':(999.,1000.,1001.,2000.)[i//4%4],'方向':(-1.,0.,1.)[i%3],
                '冰冻':(0.,1000.,1001.,0.)[i//16],'黄油':1. if i==63 else 0.}),
            dict(op='zombie64_redeye',unit=0),dict(op='zombie64_redeye',unit=0),
            dict(op='zombie64_fields',unit=0,fields={'_pvp_grab':{'id':'body-1','ticks':(74.,74.5,75.,76.)[i%4]}})])
        if i%8==0:ops.append(dict(op='zombie64_registry',id='body-1'))
        if i%8==1:ops.append(dict(op='zombie64_fields',unit=1,fields={'血量':0.}))
        if i%8==2:ops.append(dict(op='zombie64_fields',unit=1,fields={'灰烬':0.}))
        ops.extend([dict(op='zombie64_redeye',unit=0),dict(op='zombie64_landed')])
        output.append(('zombie64-red-eye-held-clocks-grab-and-launch-'+str(i),case))
    for i in range(64):
        case,ops=setup(400+i)
        ops.extend([dict(op='zombie64_configure',unit=0,name=('史莱姆僵尸','中型史莱姆','小型史莱姆','普通僵尸')[i%4],hp=100.,observed=True),
            dict(op='zombie64_fields',unit=0,fields={'血量':(0.,-1024.,-1025.,-1026.)[i//4%4],'_pvp_slime_sticky':bool(i//16%2),
                '_pvp_wave_index':7,'_pvp_seat':'zombie2'}),dict(op='zombie64_limit',value=(1,4,5,200)[i//16])])
        if i%7==0:ops.append(dict(op='zombie64_fields',unit=0,fields={'灰烬':0.}))
        if i%7==1:ops.append(dict(op='zombie64_fields',unit=0,fields={'魅惑':0.}))
        ops.extend([dict(op='zombie64_split',unit=0),dict(op='zombie64_split',unit=0),dict(op='zombie64_limit',value=200),dict(op='zombie64_drain')])
        output.append(('zombie64-slime-swallow-sticky-and-deferred-splits-'+str(i),case))
    for i in range(48):
        case,ops=setup(500+i)
        ops.extend([dict(op='zombie64_configure',unit=0,name='史莱姆僵尸',hp=100.,observed=True),
            dict(op='zombie64_fields',unit=0,fields={'血量':0.,'_pvp_slime_sticky':True}),
            dict(op='zombie64_limit',value=1),dict(op='zombie64_spawn_mode',value=('ok','none','throw_before','throw_after')[i%4]),
            dict(op='lifecycle_hook',name=('zombie64_event','zombie64_spawn','zombie64_draw')[i//4%3],
                fail_before=i//12==0,fail_after=i//12==1,body=[dict(op='zombie64_fields',unit=0,
                    fields={'位置':[950.,440.,0.,0.],'魅惑':0.,'_pvp_slime_sticky':False})] if i//12==2 else []),
            dict(op='zombie64_finish',unit=0,alive=False,catch=True),dict(op='zombie64_limit',value=200),
            dict(op='zombie64_drain',catch=True)])
        output.append(('zombie64-split-callbacks-source-capture-and-scopes-'+str(i),case))
    for i in range(32):
        case,ops=setup(600+i)
        ops.extend([dict(op='plant_fields',plant=0,fields={'_pvp_content':'甜薯'}),
            dict(op='zombie64_fields',unit=0,fields={'_pvp_content':('史莱姆僵尸','红眼巨人','传送带僵尸','掷弹兵僵尸')[i%4],
                '黄油':1.,'位置':[264.,432.,0.,0.]}),
            dict(op='tile_replace',cell=[7,4],value={'方块':'空','植物':bool(i%2)}),
            dict(op='lifecycle_hook',name='zombie64_alias',fail_before=i//4%4==0,fail_after=i//4%4==1),
            dict(op='zombie64_gate',unit=0,catch=True),dict(op='zombie64_restore_taunt')])
        output.append(('zombie64-gate-taunt-markers-and-alias-unwind-'+str(i),case))
    for i in range(32):
        case,ops=setup(700+i)
        ops.extend([dict(op='zombie64_fields',unit=0,fields={'_pvp_content':('传送带僵尸','普通僵尸')[i%2]}),
            dict(op='tile_replace',cell=[8,5],value={'方块':('梯子块','空')[i//2%2]}),
            dict(op='index',value=(0,-1,None,8)[i//4%4]),
            dict(op='zombie64_tag',name='梯子块',point=[(264.,1224.)[i//16],408.],catch=True)])
        output.append(('zombie64-installed-belt-placement-and-publish-'+str(i),case))
    for i in range(24):
        case,ops=setup(800+i)
        ops.extend([dict(op='zombie64_fields',unit=1,fields={'_pvp_thrown_by':'body-0',
            '位置':[264.,(100.,428.16,432.,576.)[i%4],0.,(-.1,0.,.1)[i//4%3]],'血量':0. if i//12 else 100.}),
            dict(op='zombie64_landed'),dict(op='zombie64_landed')])
        output.append(('zombie64-thrown-landing-and-death-boundary-'+str(i),case))
    return output


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,ContentZombie64Extension,'typed72-content-zombies64',probe_timeout=600))
