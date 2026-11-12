"""Literal chili AST against typed effects with live callback/list identity.

PvP sourced wrapper composition and whole battle acceptance remain required.
"""
import argparse
import copy
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_doom as doom
from verify_stages import sha,difference
import evidence_store
import evidence_archive
plants=doom.plants;projectiles=doom.projectiles;hero=doom.hero;patch=doom.patch;ROOT=doom.ROOT;P=doom.P
COUNTERS=('chili_fire_patch_count','chili_zombie_explode_count','chili_damage_count','chili_zombie_charmed_damage_count',
    'chili_zombie_plant_damage_count','chili_zombie_player_hit_count','chili_player_hit_count','chili_launch_block_count','chili_launch_timeout_count')
HITS='智能火命中';EXP=P+'chili_zombie_explosion_id';GLOBAL_HITS=P+'chili_zombie_player_hits';HINT=P+'chili_zombie_row_hint'


def reference():
    env=doom.reference()
    names=('is_enemy_chili_zombie_fire','chili_int_or_none','chili_enemy_fire_target_rows','chili_target_row_from_y',
        'chili_row_fallback_hit','chili_has_row_targets','chili_player_target_row','chili_x_overlap',
        'damage_player_from_chili_zombie','chili_zombie_fire_hit_plants','chili_fire_hit_one_zombie','chili_fire_hit_zombies',
        'chili_zombie_fire_hit_charmed_zombies','chili_zombie_enemy_fire_scan','chili_zombie_source_rows','chili_zombie_target_row',
        'update_chili_row_hints','snap_chili_fire_to_ground','chili_launch_lock_active','mark_chili_fire_player_hit',
        'update_chili_launch_guard','chili_fire_player_hit','patch_chili_fire_entity','chili_fire_scan','spawn_chili_zombie_fire_row',
        'play_chili_zombie_explosion')
    projectiles.functions(patch.PATCH,[P+n for n in names],env)
    env['raw_chili']={n:env[P+n] for n in names+('update_chili_zombie_row_hint',)}
    return env


class ChiliExtension(doom.DoomExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.native_time=0.;self.held_hits=[];self.dispatch=[];self.raw_chili=ref['raw_chili']
        for n in COUNTERS:self.env[P+n]=0
        self.env[P+'time']=types.SimpleNamespace(perf_counter=lambda:self.native_time)
        self.g['掉血']=self.damage_player
        def hint(g,zombie,force=False):
            self.dispatch.append(['hint',self.label(zombie),force]);self.before('hint');result=self.raw_chili['update_chili_zombie_row_hint'](g,zombie,force);self.after('hint');return result
        def enemy(g,e,l,r,t,b,s):
            self.dispatch.append(['enemy',self.birth_index(e),[l,r,t,b],s]);return self.raw_chili['chili_zombie_enemy_fire_scan'](g,e,l,r,t,b,s)
        def player(g,e,l,r,t,b,s):
            self.dispatch.append(['player',self.birth_index(e),[l,r,t,b],s]);return self.raw_chili['chili_fire_player_hit'](g,e,l,r,t,b,s)
        def units(g,e,l,r,t,b,s,charmed_only=False,target_rows=None):
            self.dispatch.append(['units',self.birth_index(e),[l,r,t,b],s,charmed_only,None if target_rows is None else sorted(target_rows)])
            return self.raw_chili['chili_fire_hit_zombies'](g,e,l,r,t,b,s,charmed_only,target_rows)
        for n,fn in (('update_chili_zombie_row_hint',hint),('chili_zombie_enemy_fire_scan',enemy),('chili_fire_player_hit',player),('chili_fire_hit_zombies',units)):
            self.env[P+n]=fn

    def birth_index(self,e):return next(i for i,v in enumerate(self.births) if e is v)
    def entity_source(self,index):return self.births[index]
    def damage_player(self,amount):
        self.calls.append(['damage',amount]);self.before('player_damage');result=self.c._player_damage(amount);self.after('player_damage');return result
    def decode_key(self,v):
        if not isinstance(v,dict):return v
        if 'unit' in v:return id(self.units[v['unit']])
        if 'plant' in v:return id(self.all_plants[v['plant']])
        if 'entity' in v:return id(self.births[v['entity']])
        return id(self.ctx.get_proxy(v['hero']))
    def encode_key(self,v):
        for name,records in (('unit',enumerate(self.units)),('plant',enumerate(self.all_plants)),('entity',enumerate(self.births)),('hero',self.c.proxies.items())):
            for k,record in records:
                if v==id(record):return {name:k}
        return v
    def encode_hits(self,h):return None if h is None else [self.encode_key(k) for k in h]
    def fire_fields(self,e,values):
        for k,v in values.items():
            e[k]=None if v is None else [self.decode_key(a) for a in v] if k==HITS else self.decode_key(v) if k==EXP else copy.deepcopy(v)
    def fire_state(self,e):
        v=copy.deepcopy(e)
        if HITS in v:v[HITS]=self.encode_hits(v[HITS])
        if EXP in v:v[EXP]=self.encode_key(v[EXP])
        if '_pvp_instant_attack' in v:v['_pvp_instant_attack_text']=str(v.pop('_pvp_instant_attack'))
        return v

    def operation(self,op):
        action=op['op'];result=None;raw=self.raw_chili
        if action=='chili_scope':
            source=self.births[op['entity_source']] if 'entity_source' in op else self.units[op['unit_source']] if 'unit_source' in op else self.ctx.sources[op['source']] if op.get('source') is not None else None
            with self.c.context(op['target'],op['owner'],op.get('phase','entities'),source):self.operations(op['body'],False)
        elif action=='fixture_fire':
            self.add_entity(op.get('name','火'),op.get('facing',1.),list(op['position']));e=self.births[-1]
            if 'source' in op:e.update(copy.deepcopy(op['source']))
            self.fire_fields(e,op.get('values',{}))
        elif action=='fire_write':self.fire_fields(self.births[op['entity']],op['values'])
        elif action=='fire_globals':
            if 'time' in op:self.native_time=op['time']
            if 'hits' in op:self.g[GLOBAL_HITS]=None if op['hits'] is None else [self.decode_key(v) for v in op['hits']]
        elif action=='hold_fire_hits':self.held_hits.append(self.births[op['entity']][HITS])
        elif action=='fire_plant_write':self.all_plants[op['plant']].update(copy.deepcopy(op['values']))
        elif action in ('fire_unit_write','fire_proxy_write'):
            target=self.units[op['target']] if action=='fire_unit_write' else self.ctx.get_proxy(op['target'])
            dict.update(target,copy.deepcopy(op['values']))
        elif action.startswith('fire_'):
            e=self.births[op['entity']] if 'entity' in op else None;s=op.get('scale',self.g['比']);rows=None if op.get('rows') is None else set(op['rows'])
            args=([self.g,e]+op['box']+[s]) if 'box' in op else []
            try:
                if action=='fire_enemy':result=raw['is_enemy_chili_zombie_fire'](e)
                elif action=='fire_rows':result=sorted(raw['chili_enemy_fire_target_rows'](e,s))
                elif action=='fire_snap':
                    result=raw['snap_chili_fire_to_ground'](self.g,e)
                    if result is not None:result=list(result)
                elif action=='fire_patch':result=raw['patch_chili_fire_entity'](self.g,e)
                elif action=='fire_spawn':result=raw['spawn_chili_zombie_fire_row'](self.g,self.units[op['unit']],op.get('friendly',False))
                elif action=='fire_scan':result=raw['chili_fire_scan'](self.g)
                elif action=='fire_hint':result=raw['update_chili_zombie_row_hint'](self.g,self.target(op['target']),op.get('force',False))
                elif action=='fire_source_rows':result=sorted(raw['chili_zombie_source_rows'](self.g,self.units[op['unit']],op.get('scale')))
                elif action=='fire_update_hints':result=raw['update_chili_row_hints'](self.g)
                elif action=='fire_mark':result=self.encode_hits(raw['mark_chili_fire_player_hit'](e))
                elif action=='fire_launch_guard':result=raw['update_chili_launch_guard'](self.g,op.get('now'))
                elif action=='fire_launch_locked':result=raw['chili_launch_lock_active'](self.g,op.get('now'))
                elif action=='fire_player_hit':result=raw['chili_fire_player_hit'](*args)
                elif action=='fire_damage_player':result=raw['damage_player_from_chili_zombie'](self.g,op['center_x'],*op['box'],s,self.decode_key(op['explosion']),rows)
                elif action=='fire_hit_plants':result=raw['chili_zombie_fire_hit_plants'](*args,target_rows=rows)
                elif action=='fire_hit_units':result=raw['chili_fire_hit_zombies'](*args,charmed_only=op.get('charmed_only',False),target_rows=rows)
                elif action=='fire_enemy_scan':result=raw['chili_zombie_enemy_fire_scan'](*args)
                else:raise ValueError(action)
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row);row['entities']=[self.fire_state(e) for e in self.g['实体']];row['effect_births']=[self.fire_state(e) for e in self.births]
        row['chili_global']=dict(time=self.native_time)
        if GLOBAL_HITS in self.g:row['chili_global']['player_hits']=self.encode_hits(self.g[GLOBAL_HITS])
        row['chili_dispatch']=self.dispatch;row['chili_counts']=[self.env[P+n] for n in COUNTERS]
        row['held_fire_hits']=[self.encode_hits(h) for h in self.held_hits]
        row['chili_unit_fields']=[{k:u[k] for k in ('冰冻',) if k in u} for u in self.units]
        row['chili_proxy_fields']={s:{k:u[k] for k in ('牛顿',HINT) if k in u} for s,u in self.c.proxies.items()}


def fire(values=None,pos=(240.,288.,.3,-.5),**extra):return dict(op='fixture_fire',position=list(pos),values=values or {},**extra)
def scope(body,**extra):return dict(op='chili_scope',target='zombie',owner='plant',phase='entities',body=body,**extra)
def base():return doom.base()


def make_cases():
    cases=[]
    for i in range(120):
        c=base();c['plant_world']['tile']=(24.,48.,80.)[i%3];s=c['plant_world']['tile'];x=(-.00001,0.,s,s+.00001,4*s,13*s)[i%6];y=(-s,0.,5.2*s,10*s,15*s)[i//6%5]
        values={}
        if i%4==0:values.update({'智能火行':None,'智能火列':None,'牛顿':None})
        if i%4==1:values.update({'智能火行':4.8,'智能火列':4.9})
        if i%7==0:values.update({'智能火地面行':7.2})
        if i%9==0:values.update({'智能火命中':['previous']})
        c['operations']=[dict(op='tile_replace',cell=[6,4],value={'方块':('石','水','黑水','花盆块')[i%4],'植物':i%2==0}),fire(values,(x,y,.3,-.5)),
            dict(op='fire_rows',entity=0),dict(op='fire_snap',entity=0),dict(op='fire_patch',entity=0),dict(op='fire_snap',entity=0),dict(op='fire_patch',entity=0)]
        cases.append(('chili-terrain-'+str(i),c))
    options=[{}, {P+'chili_zombie_fire':True},{P+'chili_zombie_fire':False},{P+'chili_zombie_friendly_fire':True},{EXP:None},{EXP:''},
        {P+'chili_fire_target_rows':None},{P+'chili_fire_target_rows':[]},{P+'chili_fire_target_rows':[None,5.9,-2.4]},
        {P+'chili_fire_target_rows':4.8},{P+'chili_fire_damage_mode':'friendly',P+'chili_zombie_fire':True},
        {P+'chili_fire_damage_mode':'enemy',P+'chili_zombie_friendly_fire':True},{P+'chili_fire_damage_mode':''},{P+'chili_fire_damage_mode':None}]
    for i,v in enumerate(options):
        for name in ('火','豌豆'):
            c=base();c['operations']=[fire(v,name=name),dict(op='fire_enemy',entity=0),dict(op='fire_rows',entity=0),dict(op='fire_patch',entity=0),dict(op='fire_enemy',entity=0),dict(op='fire_rows',entity=0)]
            cases.append(('chili-classification-'+name+'-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['玩家位置']=[240.,288.,.7,-2.];values={}
        if i%6==0:values[EXP]='tail'
        if i%6==1:values[EXP]=None
        if i%6==2:values[HITS]=['__pvz_sb_player__']
        if i%6==3:values[HITS]=None
        lock=(0.,3.,4.,-1.)[i//6%4];launch=(0.,150.)[i//24]
        c['globals'].update({'辣飞天':launch,'__pvz_sb_chili_launch_lock_until':lock})
        c['operations']=[fire(values),dict(op='fire_globals',time=3.),dict(op='fire_player_hit',entity=0,box=[200.,280.,200.,320.],catch=True),
            dict(op='fire_launch_locked'),dict(op='fire_launch_guard',now=4.),dict(op='fire_launch_guard',now=7.),dict(op='fire_mark',entity=0),dict(op='fire_patch',entity=0)]
        cases.append(('chili-launch-lock-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['模式']='正常模式' if i%4 else '我是僵尸';c['globals']['玩家位置']=[240.,288.,.1,-.2]
        explosion=({'unit':0},None,'tail',17.)[i%4];body=[fire(),dict(op='fire_globals',time=2.,hits=None if i%6==0 else list(range(256)) if i%6==1 else []),
            dict(op='fire_damage_player',center_x=(240.,241.)[i%2],explosion=explosion,box=[200.,280.,200.,350.],rows=(None,[],[9],[5])[i//4%4]),
            dict(op='fire_damage_player',center_x=240.,explosion=explosion,box=[200.,280.,200.,350.])]
        if i%3==0:body.insert(2,dict(op='lifecycle_hook',name='player_damage',fail_before=i%2==0,fail_after=i%2!=0))
        c['operations']=body;cases.append(('chili-player-damage-'+str(i),c))
    for i in range(40):
        c=base();body=[fire({HITS:[]}),dict(op='hold_fire_hits',entity=0)]
        for n in range(6):body.append(dict(op='plant_original',cell=[5,3+n//2],name='南瓜头' if n%2 else '向日葵'))
        if i%4==0:body.append(dict(op='fire_plant_write',plant=0,values={'死':None}))
        if i%4==1:body.append(dict(op='fire_plant_write',plant=1,values={'铲死':False}))
        body.append(dict(op='lifecycle_hook',name='clear',fail_before=i%5==0,fail_after=i%5==1,
            body=[dict(op='fire_write',entity=0,values={HITS:[]}),dict(op='plant_roster_replace',plants=[])] if i%3==0 else []))
        body += [dict(op='fire_hit_plants',entity=0,box=[150.,300.,220.,320.],rows=(None,[],[5],[6])[i%4],catch=True),dict(op='fire_hit_plants',entity=0,box=[150.,300.,220.,320.])]
        c['operations']=body;cases.append(('chili-plants-capture-'+str(i),c))
    for i in range(64):
        c=base();c['units']=[projectiles.unit(240.+n*20.,288.,owner='plant' if n%2 else 'zombie') for n in range(4)]
        for n in (1,3):c['units'][n]['source']['魅惑']=None if i%2 else 0.
        body=[fire({HITS:[]}),dict(op='hold_fire_hits',entity=0)]
        for n in range(4):body += [dict(op='fire_unit_write',target=n,values={'冰冻':1.}),dict(op='doom_write_unit',unit=n,values={'大小':(.1,.8,2.,None)[n]})]
        if i%3==0:body += [dict(op='lifecycle_hook',name='ash',fail_after=i%6==0,body=[dict(op='roster_replace',targets=[0,3,2]),dict(op='fire_write',entity=0,values={HITS:[]})])]
        body += [dict(op='fire_hit_units',entity=0,box=[200.,340.,100.,340.],charmed_only=i%2==0,rows=(None,[],[5],[9])[i//2%4]),dict(op='fire_hit_units',entity=0,box=[200.,340.,100.,340.])]
        c['operations']=[scope(body,unit_source=0)];cases.append(('chili-unit-capture-'+str(i),c))
    for i in range(48):
        c=base();c['seed']=9100+i;c['units'] += [projectiles.unit(150.+n*48.,432.,owner='plant' if n%2 else 'zombie') for n in range(5)]
        for n in (1,3,5):c['units'][n]['source']['魅惑']=0.
        body=[dict(op='plant_original',cell=[9,3+n],name='向日葵') for n in range(5)]
        if i%4==0:body += [dict(op='lifecycle_hook',name='add',fail_before=i%8==0,fail_after=i%8!=0)]
        if i%4==1:body += [dict(op='lifecycle_hook',name='add',body=[dict(op='effect_roster_replace',births=[])])]
        body += [dict(op='fire_spawn',unit=0,friendly=i%2==0),dict(op='fire_scan'),dict(op='fire_scan')]
        c['operations']=[scope(body,unit_source=0)];cases.append(('chili-spawn-scan-'+str(i),c))
    for i in range(24):
        c=base();c['globals']['模式']='正常模式';c['globals']['玩家位置']=[240.,288.,0.,0.]
        c['operations']=[fire({HITS:None,P+'chili_zombie_fire':i%2==0}),dict(op='plant_original',cell=[5,4],name='向日葵'),
            dict(op=('fire_hit_plants','fire_hit_units','fire_enemy_scan')[i%3],entity=0,box=[150.,350.,100.,350.],catch=True),
            dict(op='fire_mark',entity=0),dict(op='fire_patch',entity=0)]
        cases.append(('chili-null-hit-list-'+str(i),c))
    for i in range(48):
        c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2'];c['sources']=[{'名':'火','_pvp_owner':'plant'}]
        for h in c['heroes'].values():h['玩家位置']=[240.,288.,0.,-.3];h['模式']='正常模式'
        c['units'][0]['source']['魅惑']=0.
        body=[fire({P+'chili_zombie_friendly_fire':True}),dict(op='fire_proxy_write',target='zombie',values={'牛顿':(None,0.,.1)[i%3],HINT:(None,5.,9.)[i%3]}),
            dict(op='fire_update_hints'),dict(op='fire_hint',target='zombie',force=i%2==0)]
        body += [scope([dict(op='fire_hit_units',entity=0,box=[180.,300.,100.,340.],charmed_only=i%4==0,rows=(None,[],[5],[9])[i%4])],entity_source=0),
            scope([dict(op='fire_player_hit',entity=0,box=[180.,300.,100.,340.])],entity_source=0),
            scope([dict(op='fire_enemy_scan',entity=0,box=[180.,300.,100.,340.])],entity_source=0)]
        c['operations']=body;cases.append(('chili-hero-composition-'+str(i),c))
    for i in range(48):
        c=base();body=[fire({P+'chili_zombie_friendly_fire':True}),dict(op='fire_unit_write',target=0,values={'牛顿':(.0,.1,None)[i%3],HINT:(None,4.,9.)[i//3%3]}),
            dict(op='fire_source_rows',unit=0),dict(op='fire_hint',target=0,force=i%2==0),dict(op='fire_source_rows',unit=0)]
        body += [dict(op='lifecycle_hook',name='hint',fail_before=i%6==0,fail_after=i%6==1,body=[dict(op='effect_roster_replace',births=[]),fire()]),dict(op='fire_scan')]
        c['operations']=body;cases.append(('chili-scan-captured-list-'+str(i),c))
    for i in range(48):
        c=base();s=48.;x=240.;y=288.;edge=i%4;delta=(0.,1e-7,-1e-7)[i//4%3];box=[x-20.,x+20.,y-20.,y+20.]
        kind=('fire_player_hit','fire_hit_units','fire_hit_plants')[i//12%3]
        half=.38*s if kind=='fire_player_hit' else .36*s if kind=='fire_hit_units' else .48*s
        up=.95*s if kind=='fire_player_hit' else 1.9*s if kind=='fire_hit_units' else .62*s
        down=.20*s if kind=='fire_player_hit' else .16*s if kind=='fire_hit_units' else .42*s
        if kind=='fire_hit_plants':x=4*s+.5*s;y=5*s+.45*s;box=[x-20.,x+20.,y-20.,y+20.]
        if edge==0:box[0]=x+half+delta;box[1]=box[0]+40.
        elif edge==1:box[1]=x-half-delta;box[0]=box[1]-40.
        elif edge==2:box[2]=y+down+delta;box[3]=box[2]+40.
        else:box[3]=y-up-delta;box[2]=box[3]-40.
        c['globals']['玩家位置']=[240.,288.,0.,0.]
        c['operations']=[fire(),dict(op='plant_original',cell=[5,4],name='向日葵'),dict(op=kind,entity=0,box=box),dict(op=kind,entity=0,box=box)]
        cases.append(('chili-inclusive-boundary-'+str(i),c))
    for i in range(16):
        c=base();c['globals']['模式']='正常模式';c['globals']['玩家位置']=[240.,288.,.1,-.2]
        body=[dict(op='lifecycle_hook',name='player_damage',body=[dict(op='write',target='globals',values={'玩家位置':[600.,500.,7.,8.],'玩家血量':40.}),dict(op='fire_globals',hits=[])],fail_after=i%2==0),
            dict(op='fire_damage_player',center_x=240.,explosion=None,box=[200.,280.,200.,350.]),dict(op='fire_damage_player',center_x=240.,explosion=None,box=[200.,280.,200.,350.])]
        if i%4==0:body.insert(0,dict(op='write',target='globals',erase=['玩家血量']))
        if i%4==1:body.insert(0,dict(op='write',target='globals',values={'玩家血量':None}))
        c['operations']=body;cases.append(('chili-player-callback-replace-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=plants.protection.reference();chili_ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:ChiliExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-chili-effects',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['sourced PvP death wrapper binding','full HeroProxy template constructor','full battle','network/replay','dynamic invalid record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
