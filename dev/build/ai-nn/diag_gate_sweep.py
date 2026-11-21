"""Gate-threshold sweep: does less network control move the zombie champion toward r22?"""
import json,copy,sys
from concurrent.futures import ThreadPoolExecutor
from diag_common import *
from league_data import sha
CHAMP=Path(day.read(day.BATTLE/'sealed.json')['sides']['zombie']['champ'])
f=day.fixtures();CASES=f['train']+f['validation']
OPP={'r22':'r22','H':day.meta()['pool']['H']}
OFFS=[0.,-0.5,-1.,-2.,-100.]
W=OUT/'gate';W.mkdir(parents=True,exist_ok=True)
def variant(off):
    if off==0:return str(CHAMP)
    d=day.read(CHAMP);d['switch']['native_gate']['bias']=[b+off for b in d['switch']['native_gate']['bias']]
    p=W/f'zombie-gate{off:+g}.json';p.write_text(json.dumps(d),encoding='utf8');return str(p)
models={o:variant(o) for o in OFFS};models['r22']='r22'
jobs=[(m,o,c) for m in models for o in OPP for c in CASES]
def run(job):
    m,o,c=job;g=game(c,OPP[o],models[m],W/'store');h,t=trace(g)
    sw=[e for e in t.get('switches',[]) if e.get('phase')=='special']
    deploys=[a for a in t['activity'] if a['kind']=='deploy' and a['side']=='zombie']
    return dict(model=str(m),opp=o,case=c,winner=(t['result'] or {}).get('winner'),timeout=t['timeout'],time=t['time'],
                battle=t['log_sha256'],special=len(sw),on=sum(e['choice']!=0 for e in sw),zdeploy=len(deploys))
with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv)>1 else 8) as p:res=list(p.map(run,jobs))
(W/'sweep.json').write_text(json.dumps(res,ensure_ascii=False,indent=0),encoding='utf8')
