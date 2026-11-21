import json,sys,glob
from collections import defaultdict
from diag_common import *
from league_data import sha
W=OUT/'gate';CHAMP=day.read(day.BATTLE/'sealed.json')['sides']['zombie']['champ']
names={sha(Path(CHAMP)):'+0'}
for p in W.glob('zombie-gate*.json'):names[sha(p)]=p.stem.replace('zombie-gate','')
H=sha(Path(day.meta()['pool']['H']))
res=defaultdict(lambda:defaultdict(list))
for r in glob.glob(str(W/'store/games/*.receipt.json')):
    d=json.load(open(r,encoding='utf8'));p=d['parameters']
    m=names.get(p['policy'],'r22') if p['policy'] else 'r22'
    o='H' if p['plant']==H else 'r22' if p['plant'] is None else '?'
    res[(m,o)][p['opening']+p['corpus']].append(d)
for k in sorted(res):
    v=[x[0] for x in res[k].values()]
    w=sum(x['winner']=='zombie' and not x['timeout'] for x in v);to=sum(x['timeout'] for x in v)
    print(k,len(v),'zwin',w,'timeout',to,'avg t',round(sum(x['time'] for x in v)/len(v),1))
