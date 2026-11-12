"""Literal 1.5.0.1 AST + original bytecode differential for damage wrappers.

Effect callbacks are synchronous observed boundaries, NOT implemented terrain
or spawn logic. Explicit frame fixtures test direct native call-site conditions;
PvP dispatch tests supply no direct native caller. Full driver binding remains
separate. This suite must never count as a whole-battle acceptance test.
"""
import argparse
import ast
import builtins
import copy
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import verify_protection as protection
import verify_targets as targets
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT
PATCH=hero.REF/'modkit/pvzrouge_runtime_patch_source_20260904.py'
PREFIX='__pvz_sb_'
COUNTERS=dict(charm_bite='gravebuster_zombie_zombie_bite_damage_count',blue_damage='tri_damage_boost_count',
    blue_surface='tri_surface_boost_count',squash_skipped='squash_zombie_native_skip_count',
    chili_skipped='chili_native_skip_count',pumpkin_sound='pumpkin_armor_sound_count')


def patch_reference():
    names=('float','randint','is_charmed_zombie','is_gravebuster_zombie','has_charm_secret','zombie_bite_damage',
        'charm_bite_pair_from_frame','adjust_charm_bite_damage','is_enemy_squash_zombie_entity',
        'native_enemy_squash_entity_from_caller','is_native_chili_ash_call','remember_zombie_max_hp',
        'pumpkin_armor_should_sound','play_pumpkin_armor_sound','wrap_damage_zombie','wrap_surface_damage_zombie',
        'wrap_ash_zombie','wrap_knockback_zombie','maybe_trigger_chili_zombie_death','maybe_trigger_doom_zombie_death',
        'maybe_trigger_gravebuster_zombie_death','maybe_trigger_plant_zombie_death_effects')
    tree=ast.parse(PATCH.read_text(encoding='utf8'),str(PATCH));selected=[];constants={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            try:value=ast.literal_eval(node.value)
            except (ValueError,TypeError,SyntaxError):continue
            for t in node.targets:
                if isinstance(t,ast.Name) and t.id.startswith(PREFIX):constants[t.id]=value
        elif isinstance(node,ast.FunctionDef) and node.name in {PREFIX+n for n in names}:selected.append(node)
    if len(selected)!=len(names):raise ValueError('missing patch source functions')
    return constants,compile(ast.Module(body=selected,type_ignores=[]),str(PATCH),'exec')


class PatchExtension(targets.TargetExtension):
    def __init__(self,ctx,case,pref,reference):
        super().__init__(ctx,case,pref);self.effect_calls=[];self.cfg=case['patch']
        for u,fields in zip(self.units,self.cfg['units']):u.update(copy.deepcopy(fields))
        self.empty_frame=types.SimpleNamespace(f_code=types.SimpleNamespace(co_name='callback'),f_lasti=-1,f_locals={},f_globals={})
        self.frame=self.empty_frame
        constants,code=reference;env=copy.deepcopy(constants);env['__builtins__']=builtins.__dict__
        env[PREFIX+'sys']=types.SimpleNamespace(_getframe=lambda depth:self.frame)
        env[PREFIX+'log']=lambda *args:None
        exec(code,env);self.env=env
        for key in COUNTERS.values():env[PREFIX+key]=0
        for key in ('damage','surface_damage','ash','knockback'):env[PREFIX+key+'_wrap_done']=False
        for key,name in (('update_chili_zombie_row_hint','hint'),('spawn_chili_zombie_fire_row','chili'),
                         ('spawn_doom_zombie_explosion','doom'),('place_grave_from_gravebuster_zombie','remnant'),
                         ('spawn_gravebuster_plant_from_zombie','plant')):
            def callback(game,u,name=name,**kw):
                call=[name,self.unit_index(u)]
                if name=='hint':call.append(kw.get('force',False))
                if name=='chili':call.append(kw.get('friendly',False))
                self.effect_calls.append(call)
                if self.cfg.get('mutate_kind'):u['植物僵尸名']=self.cfg['mutate_kind']
                if self.cfg.get('fail_effect')==name:raise RuntimeError('injected effect failure')
                return self.cfg.get('effect_result',True)
            env[PREFIX+key]=callback
        for name in ('伤害僵尸','表面伤害僵尸','灰烬僵尸','击退僵尸'):self.g[name]=types.FunctionType(ctx.functions[name],self.g)
        for name in ('damage_zombie','surface_damage_zombie','ash_zombie','knockback_zombie'):env[PREFIX+'wrap_'+name](self.g)
        self.wrapped={n:self.g[n] for n in ('伤害僵尸','表面伤害僵尸','灰烬僵尸','击退僵尸')}
        for native,label in (('伤害僵尸','ordinary'),('表面伤害僵尸','surface'),('灰烬僵尸','ash')):
            def entry(index,*args,native=native,label=label):
                self.raw_calls.append([label,self.unit_index(self.g['僵尸'][index])]+list(args));old=self.frame;self.frame=self.empty_frame
                try:return self.wrapped[native](index,*args)
                finally:self.frame=old
            self.c.originals[native]=entry
        self.g.update(伤害僵尸=self.c._zombie_damage,表面伤害僵尸=self.c._surface_damage,灰烬僵尸=self.c._ash_damage)

    def make_frame(self,origin):
        local={};fg=dict(self.g);lasti=-1;code='direct_fixture'
        if origin.get('charm_bite'):lasti=72400
        if 'current' in origin:local['l']=next(i for i,u in enumerate(self.g['僵尸']) if u is self.units[origin['current']])
        if 'other' in origin:local['z']=next(i for i,u in enumerate(self.g['僵尸']) if u is self.units[origin['other']])
        if origin.get('entity') is not None:
            e=origin['entity'];entity={}
            if e.get('enemy_squash'):entity.update(__pvz_sb_squash_zombie_entity=True,__pvz_sb_squash_zombie_friendly=False)
            if e.get('blue'):entity['三向蓝火弹']=True
            if e.get('tracking'):entity['追踪']=None
            local.setdefault('l',0);fg['实体']=[{} for _ in range(local['l'])]+[entity]
        else:fg['实体']=[]
        if origin.get('horizontal_chili'):code='<module>';fg['name']='火爆辣椒';lasti=117000
        return types.SimpleNamespace(f_code=types.SimpleNamespace(co_name=code),f_lasti=lasti,f_locals=local,f_globals=fg)

    def operation(self,op):
        action=op['op'];result=None
        if action=='direct_hit':
            u=self.units[op['unit']];index=next(i for i,t in enumerate(self.g['僵尸']) if t is u)
            old=self.frame;self.frame=self.make_frame(op.get('origin',{}))
            try:
                native={'ordinary':'伤害僵尸','surface':'表面伤害僵尸','ash':'灰烬僵尸'}[op['kind']]
                args=[] if op['kind']=='ash' else [op.get('facing',1.),op['amount']]
                result=self.wrapped[native](index,*args)
            finally:self.frame=old
        elif action=='death_trigger':result=self.env[PREFIX+'maybe_trigger_plant_zombie_death_effects'](self.g,self.units[op['unit']])
        elif action=='knockback':
            u=self.units[op['unit']];index=next(i for i,t in enumerate(self.g['僵尸']) if t is u)
            result=self.wrapped['击退僵尸'](index,op['amount'])
        elif action=='max_hp':
            u=self.units[op['unit']];u['血量']=op['hp'];self.env[PREFIX+'remember_zombie_max_hp'](u)
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row)
        keys=('植物僵尸','植物僵尸名','__pvz_sb_chili_zombie_exploded','__pvz_sb_doom_zombie_exploded',
              '__pvz_sb_gravebuster_zombie_done','__pvz_sb_zombie_observed_max_hp','__pvz_sb_plant_zombie_max_hp')
        row['patch_units']=[{k:u[k] for k in keys if k in u} for u in self.units]
        row['patch_counters']={key:self.env[PREFIX+value] for key,value in COUNTERS.items()}
        row['effect_calls']=self.effect_calls


def make_cases():
    cases=[]
    def base(n=1):
        c=hero.base();c['sources']=[{}];c['units']=[dict(body={'僵尸':'普通僵尸','防具':'','手持':'','血量':100.,'防具血量':0.,
            '手持血量':0.,'方向':1.,'位置':[100.,200.,0.,0.],'受伤':0.,'手持受伤':0.},source={'_pvp_owner':'zombie'}) for _ in range(n)]
        c['patch']=dict(units=[{'大小':1.,'入水':False} for _ in range(n)]);c['damage']=dict(watch_armor=True);return c
    for i in range(144):
        c=base();u=c['units'][0];s=c['patch']['units'][0]
        u['body'].update(防具=('','路障','南瓜头防具')[i%3],防具血量=(0.,50.,100.)[i%3],手持=('','钢门','梯子','气球','报纸','玩偶匣')[i%6],手持血量=(0.,30.,100.)[i%3])
        if i%7==0:u['body']['灰烬']=0.
        s.update(植物僵尸=i%2==0,植物僵尸名=('普通僵尸','辣椒僵尸','毁灭菇僵尸','墓碑吞噬者僵尸')[i%4])
        if i%9==0:u['source']['魅惑']=None
        c['operations']=[dict(op='direct_hit',unit=0,kind='surface' if n%2 else 'ordinary',amount=(0.,10.,29.,30.,50.,200.)[n],facing=-1.,
            origin=dict(entity=dict(blue=bool(i%2),enemy_squash=i%5==0,tracking=i%4==0))) for n in range(6)]
        c['operations']+=[dict(op='unit_hit',target=0,kind='ordinary',amount=10.),dict(op='death_trigger',unit=0)]
        cases.append(('damage-wrapper-%d'%i,c))
    for i in range(96):
        c=base();u=c['units'][0];s=c['patch']['units'][0]
        s['植物僵尸名']=('辣椒僵尸','毁灭菇僵尸','墓碑吞噬者僵尸','普通僵尸')[i%4]
        u['body']['血量']=(-1001.,-1000.,-999.,-1.,0.,1.)[(i//4)%6]
        if i%5==0:u['source']['魅惑']=0.
        if i%7==0:u['body']['灰烬']=None
        if i%3==0:s['__pvz_sb_chili_zombie_exploded']=None;s['__pvz_sb_doom_zombie_exploded']=False
        c['patch']['fail_effect']=('','hint','chili','doom','remnant','plant')[i%6]
        c['patch']['effect_result']=i%2==0
        if i>=72:c['patch']['mutate_kind']='毁灭菇僵尸'
        c['operations']=[dict(op='death_trigger',unit=0),dict(op='death_trigger',unit=0)]
        cases.append(('death-selection-%d'%i,c))
    # A Cartesian block prevents parity correlations from hiding a failed
    # row-hint callback on an otherwise eligible chili death.
    for kind in ('辣椒僵尸','毁灭菇僵尸','墓碑吞噬者僵尸'):
        for fail in ('','hint','chili','doom','remnant','plant'):
            c=base();c['units'][0]['body']['血量']=0.;c['patch']['units'][0]['植物僵尸名']=kind
            c['patch']['fail_effect']=fail
            if fail=='plant':c['units'][0]['source']['魅惑']=None
            c['operations']=[dict(op='death_trigger',unit=0),dict(op='death_trigger',unit=0)]
            cases.append(('death-exception-'+kind+'-'+fail,c))
    for i in range(64):
        c=base(3)
        c['units'][0]['source']['魅惑']=None
        if i%4==0:c['units'][1]['source']['魅惑']=0.
        c['patch']['units'][i%2]['植物僵尸名']='墓碑吞噬者僵尸'
        if i%2==0:c['globals']['秘籍'].append('魅惑')
        c['operations']=[dict(op='direct_hit',unit=n,kind='ordinary',amount=1.,origin=dict(current=0,other=1,charm_bite=i%3!=0)) for n in (0,1,2)]
        cases.append(('charm-bite-%d'%i,c))
    for i in range(120):
        c=base();s=c['patch']['units'][0];u=c['units'][0]
        s['植物僵尸抗击退']=(None,False,True,-1.,0.,.5,1.,2.)[i%8];s['植物僵尸名']='高坚果僵尸' if i%3==0 else '坚果僵尸'
        feature=i%10
        if feature==1:u['body']['防具']='橄榄球头盔'
        if feature==2:s['大小']=2.1
        if feature==3:s['狂暴']=None
        if feature==4:s['撑杆']=0.
        if feature==5:u['body']['手持']='海豚';s['入水']=True
        if feature==6:u['body']['手持']='玩偶匣';u['body']['血量']=0.
        if feature==7:s['跳舞']=1.
        if feature==8:s['跳舞']=1.;u['body']['血量']=0.
        if feature==9:u['body']['防具']='黑橄榄球头盔'
        c['operations']=[dict(op='knockback',unit=0,amount=a) for a in (-2.,1.,0.,4.)]
        cases.append(('knockback-%d'%i,c))
    for i in range(48):
        c=base();u=c['units'][0];u['body']['血量']=(300.,501.,900.)[i%3]
        if i%4==0:u['body']['僵尸']='巨人僵尸'
        c['damage']['bosses']=['巨人僵尸'];c['patch']['units'][0]['植物僵尸名']='辣椒僵尸'
        c['operations']=[dict(op='direct_hit',unit=0,kind='ash',origin=dict(horizontal_chili=i%2==0,entity=dict(enemy_squash=i%3==0))),
            dict(op='unit_hit',target=0,kind='ash'),dict(op='death_trigger',unit=0)]
        cases.append(('ash-wrapper-%d'%i,c))
    for i in range(18):
        c=base();s=c['patch']['units'][0];s['植物僵尸']=(True,False,None)[i%3]
        if i%2==0:s['__pvz_sb_zombie_observed_max_hp']=None
        if i%3==0:s['__pvz_sb_plant_zombie_max_hp']=300.
        c['operations']=[dict(op='max_hp',unit=0,hp=hp) for hp in (-1.,0.,100.,50.,200.,400.)]
        cases.append(('remember-max-%d'%i,c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(args.exe).resolve()
    paths=[exe,PATCH,Path(__file__).resolve(),ROOT/'tools/typed72/patch_probe.cpp',ROOT/'tools/typed72/targets_probe.cpp',
        ROOT/'tools/typed72/hero_probe.cpp',ROOT/'tools/typed72/verify_targets.py',ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_protection.py',
        ROOT/'tools/typed72/verify_stages.py',hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,
        protection.PROTECTION,protection.TEAMS,ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths}
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=protection.reference();patchref=patch_reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:PatchExtension(ctx,c,pref,patchref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%40==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-damage-patch',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,excluded=['death effect terrain/spawn bodies','PvP sourced binding of death callbacks','full world tick','full multiplayer/replay'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
