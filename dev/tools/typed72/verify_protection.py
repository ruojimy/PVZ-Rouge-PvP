"""Differential verification of current PvP72 numeric unit protection policy."""
import argparse
import ast
import copy
import json
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_heroes import ROOT,REF,TARGETS,ZSECRETS,ZCATALOG,BATTLE,BALANCE,PHYSICS,CATALOG,RAW,PROXY_REFERENCE_PATHS,constant,selected_class,load_reference
from verify_stages import sha,difference
import evidence_store
import evidence_archive

PROTECTION=ROOT/'tools/pvp72_sources/native_protection.py'
TEAMS=REF/'modkit/pvp/teams.py'


def reference():
    env=load_reference()[0]
    tree=ast.parse(TEAMS.read_text(encoding='utf8'),str(TEAMS))
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='team_of'],type_ignores=[]),str(TEAMS),'exec'),env)
    names=('seat_has','has','holders','_own','adjust','damage_factor','shield_first','selected_grave','_relic','berserk','focused')
    secrets=selected_class(ZSECRETS,names,'PolicySecretsOracle',env)
    protection=selected_class(PROTECTION,('amount','multiplier'),'ProtectionOracle',env)
    for key in ('TYPE2','FOCUS_TICKS','FOCUS_GUARD','TILE_HZ','RELIC_SECONDS','RELIC_DEATHMATCH_SECONDS'):
        # FOCUS_TICKS has a numeric constant expression rather than a literal.
        if key=='FOCUS_TICKS':continue
        env[key]=constant(ZSECRETS,key)
    tree=ast.parse(ZSECRETS.read_text(encoding='utf8'),str(ZSECRETS))
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FOCUS_TICKS' for t in n.targets)],type_ignores=[]),str(ZSECRETS),'exec'),env)
    env['SELECTED_GRAVE_FACTOR']=constant(PROTECTION,'SELECTED_GRAVE_FACTOR')
    return env,secrets,protection


def oracle(case,ref):
    env,Secrets,Protection=ref;units=copy.deepcopy(case['units']);events=[]
    c=env['NativeTargets'].__new__(env['NativeTargets']);c.heroes={s:{} for s in ('plant','zombie','plant2','zombie2')};c.active=None;c.g={}
    b=types.SimpleNamespace(engine=types.SimpleNamespace(native_tick=0),targets=c,time=0.,deathmatch=False,
        players={s:{} for s in c.heroes})
    def emit(event_type,**data):events.append(dict(type=event_type,**data))
    b._emit=emit
    z=Secrets();z.b=b;z.by_seat={s:env['names'](case['players'].get(s,[])) for s in ('zombie','zombie2')}
    z.team=set().union(*z.by_seat.values());z.enabled=bool(z.team);z.last_stand={};b.zsecrets=z
    p=Protection();p.b=b;p.until=case['until'];p.factor=case['factor'];env['CARDS']={k:dict(producer=v) for k,v in case['cards'].items()}
    out=[]
    for op in case['operations']:
        if 'tick' in op:b.engine.native_tick=op['tick']
        if 'time' in op:b.time=op['time']
        if 'deathmatch' in op:b.deathmatch=op['deathmatch']
        if 'last_stand' in op:z.last_stand={'zombie':99.} if op['last_stand'] else {}
        if 'owner' in op:c.active=dict(target='plant',owner=op['owner'],phase='other',source=None) if op['owner'] is not None else None
        for s,uid in op.get('selected',{}).items():b.players[s]['selected_grave']=uid
        target=units[op['unit']];fn=op['function']
        if fn=='amount':value=p.amount(target,op['amount'])
        elif fn=='multiplier':value=p.multiplier(target)
        elif fn=='damage_factor':value=z.damage_factor(target)
        elif fn=='shield_first':value=z.shield_first(target)
        elif fn=='focused':value=z.focused(target)
        elif fn=='berserk':value=z.berserk()
        elif fn=='selected':value=z.selected_grave(target)
        else:raise ValueError(fn)
        rows=[]
        for u in units:
            row={'血量':u['血量'],'手持':u.get('手持',''),'手持血量':u.get('手持血量',0.)}
            row.update({k:u[k] for k in ('_pvp_zs_hurt','_pvp_zs_relic_until','_pvp_reaper_hurt','_pvp_zs_locked') if k in u});rows.append(row)
        out.append(copy.deepcopy(dict(result=value,units=rows,events=events)))
    return out


def make_cases():
    rng=random.Random(728813);cases=[]
    def base():return dict(players={},cards={'producer':True,'zombie:投篮车僵尸':False,'zombie:报纸僵尸':False},until=2500,factor=.25,units=[],operations=[])
    secrets=('专注啃咬','狂暴','阿姆斯特朗','坤坤','解除封印','遗骸','二手','僵王出品')
    for i in range(256):
        c=base();c['players']={'zombie':['zsecret:'+s for bit,s in enumerate(secrets) if i&(1<<bit)]}
        c['units']=[{'血量':100.,'_pvp_owner':'zombie','_pvp_card':'zombie:报纸僵尸','手持':'','_pvp_zs_crowd_factor':.25},
                    {'血量':100.,'_pvp_owner':'zombie','_pvp_card':'zombie:投篮车僵尸','篮球':3.,'_pvp_content':'死神僵尸'},
                    {'血量':100.,'_pvp_owner':'zombie','_pvp_card':'producer','_pvp_grave':True,'_pvp_id':'g1'},
                    {'血量':100.,'_pvp_owner':'zombie','手持':'钢门','手持血量':10.}]
        ops=[]
        for tick in (-1,0,1249,1250,2499,2500,7000):
            for u in range(4):
                ops.append(dict(function='damage_factor',unit=u,tick=tick,deathmatch=i%2==0,last_stand=i%3==0))
                ops.append(dict(function='amount',unit=u,amount=100.,selected={'zombie':'g1'}))
                ops.append(dict(function='amount',unit=u,amount=.25))
                ops.append(dict(function='shield_first',unit=u))
        c['operations']=ops;cases.append(('secret-mask-%d'%i,c))
    for i in range(96):
        c=base();c['players']={'plant':['zsecret:遗骸'],'zombie2':['zsecret:'+s for s in secrets]}
        unit={'血量':rng.choice((0.,.005,1.,50.,300.)),'_pvp_card':rng.choice(('producer','zombie:投篮车僵尸','zombie:报纸僵尸','unknown',None)),
              '手持':rng.choice(('','报纸','钢门','梯子','铁栅门','传送带','气球')),'手持血量':rng.choice((-1.,0.,1.)),
              '_pvp_grave':bool(i%2),'_pvp_hero':i%19==0,'_pvp_anchor_until':rng.choice((-1.,0.,1251.,2500.)),
              '_pvp_zs_crowd_factor':rng.choice((None,0.,.25,1.,1.5)),'篮球':rng.choice((0.,1.)),
              '_pvp_zs_lock_done':bool(i%2),'_pvp_content':'死神僵尸'}
        owners=('missing',None,'','unknown','plant','plant2','zombie','zombie2')
        owner=owners[i%len(owners)]
        if owner!='missing':unit['_pvp_owner']=owner
        if i%4==0:unit['魅惑']=None
        if i%7==0:unit['植物']=None
        if i%5==0:unit['_pvp_zs_relic_until']=None
        if i%3==0:unit['_pvp_id']='g1'
        c['units']=[unit]
        for tick in (-1,0,1,1249,1250,1251,2500,10000):
            for amount in (-1.,0.,.005,1.,49.,1000.):
                c['operations'].append(dict(function='amount',unit=0,amount=amount,tick=tick,owner='zombie',deathmatch=i%2==0,last_stand=i%3==0,selected={'zombie2':'g1' if i%2 else None}))
            for fn in ('focused','berserk','selected','shield_first','multiplier'):c['operations'].append(dict(function=fn,unit=0))
        cases.append(('boundary-%d'%i,c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(args.exe).resolve()
    paths=[exe,Path(__file__).resolve(),ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_stages.py',
           ROOT/'tools/typed72/protection_probe.cpp',PROTECTION,TARGETS,ZSECRETS,ZCATALOG,TEAMS,BATTLE,BALANCE,PHYSICS,CATALOG,RAW,
           ROOT/'src/core/pyrandom.h',ROOT/'third_party/nlohmann/json.hpp']+list((ROOT/'src/sim/typed').glob('*.*'))
    paths+=PROXY_REFERENCE_PATHS
    paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=oracle(c,ref);diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n')
                row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%32==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    summary=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-unit-protection',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),
        tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['native damage/armor wrapper chain','death effect callbacks','live card registration','full tick'])
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=summary['passed'])


if __name__=='__main__':sys.exit(main())
