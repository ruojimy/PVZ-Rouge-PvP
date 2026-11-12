"""Isolated same-rule scalar/dynamic C vs optimized D tick-by-tick comparison.

Uses the existing approved numeric tolerance/address exclusions. RNG remains
in the comparison. Never overwrites extract/oracle or the 71 reference.
"""
import argparse,hashlib,itertools,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from oracle_diff import walk
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--exe',default=str(ROOT/'build/Release/run_battle.exe'));args=ap.parse_args()
    sys.stdout.reconfigure(encoding='utf8');out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);(out/'scenarios').mkdir();rows=[]
    source=ROOT/'tools/scenarios';names='empty basic zombie_swarm projectile_storm mixed_late_game hero_inputs grave_economy duo_basic coop_waves'.split()
    names+=sorted(p.stem for p in source.glob('*.json') if p.stem.startswith(('cards_','secrets_')))
    configs={}
    for name in names:
        path=source/('_expanded_'+name+'.json')
        if not path.exists():path=source/(name+'.json')
        dest=out/'scenarios'/(name+'.json');dest.write_bytes(path.read_bytes());configs[name]=dest
    custom={'map':'家院','seed':301,'weather':'clear','durable_heroes':True,'room_ticks':16,
        'decks':{'plant':['plant:豌豆射手','plant:向日葵','plant:甜薯','plant:大喷菇','secret:雷霆'],
                 'zombie':['zombie:脑光墓碑','zombie:普通僵尸','zombie:海盗船长','zombie:乌鸦','zsecret:玉米卷']},
        'setup':[{'op':'command','value':'attack'}]}
    for i in range(16):custom['setup'].append({'op':'plant','name':'甜薯' if i%5==0 else '豌豆射手','col':30+i,'row':18})
    for i in range(24):custom['setup'].append({'op':'spawn','card':'zombie:海盗鹦鹉' if i%2 else 'zombie:乌鸦','side':'zombie','x':(44+i*.2)*48,'y':18*48,'facing':-1})
    p=out/'scenarios/native_target_routes72.json';p.write_text(json.dumps(custom,ensure_ascii=False),encoding='utf8');configs['native_target_routes72']=p
    pinned={str(Path(args.exe).resolve()):sha(args.exe)}
    pinned.update({str(p):sha(p) for p in (ROOT/'extract/data').glob('*.json')})
    pinned.update({str(p):sha(p) for p in configs.values()})
    (out/'pinned-inputs.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for name,config in configs.items():
        paths=[];error=None
        for variant in ('C','D'):
            path=out/(name+'-'+variant+'.jsonl');paths.append(path);env=os.environ.copy();env.pop('PVZ72_REFERENCE',None)
            if variant=='C':env['PVZ72_REFERENCE']='1'
            env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'userdata'/(name+variant)),PVP_HERO_GUARD='1',PVP_HERO_GUARD_LOG=str(out/(name+'-'+variant+'.hero.jsonl')))
            with (out/(name+'-'+variant+'.log')).open('wb') as log:
                result=subprocess.run([args.exe,str(config),str(path)],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
            if result.returncode:error='Process '+variant+' exited '+str(result.returncode);break
        count=0;difference=None
        if error is None:
            with paths[0].open(encoding='utf8') as left,paths[1].open(encoding='utf8') as right:
                for count,pair in enumerate(itertools.zip_longest(left,right),1):
                    a,b=pair
                    if a is None or b is None:difference={'line':count,'reason':'Unequal output lengths'};break
                    aa,bb=json.loads(a),json.loads(b);found=[];walk(aa,bb,'',found,1e-9,5)
                    if found:difference={'line':count,'tick':aa.get('t'),'fields':found,'rng_C':aa.get('rng'),'rng_D':bb.get('rng')};break
            if not count:error='Empty trace'
        row={'scenario':name,'passed':error is None and difference is None,'compared_lines':count,'error':error,'first_difference':difference}
        if all(p.exists() for p in paths):row['traces_sha256']={v:sha(p) for v,p in zip(('C','D'),paths)}
        rows.append(row);(out/'summary.json').write_text(json.dumps({'complete':False,'results':rows},ensure_ascii=False,indent=2),encoding='utf8')
        print('PASS' if row['passed'] else 'FAIL',name,count,error or '',flush=True)
    changed=[p for p,digest in pinned.items() if sha(p)!=digest]
    success=not changed and all(r['passed'] for r in rows)
    (out/'summary.json').write_text(json.dumps({'complete':True,'passed':success,'count':len(rows),'rng_compared':True,'tolerance':1e-9,'changed_inputs':changed,'results':rows},ensure_ascii=False,indent=2),encoding='utf8')
    raise SystemExit(0 if success else 1)
if __name__=='__main__':main()
