"""Measure reliance on r22 suggestion features, holding the decision scheduler fixed."""
from pathlib import Path
from position_train import OUT, HOME, BASE, MODELS, group, read, write, sha, report_comparison


def run():
    model=Path(read(OUT/'zombie-frozen.json')['model'])
    original=read(model)
    cols=[7,8,9,30]
    for col in cols:
        original['weights'][col]=0.
        for row in original['hidden']:row[col]=0.
    root=OUT/'hint-ablation'
    altered=root/'model.json';write(altered,original)
    meta=read(OUT/'generalization-plan.json')['per_opening']
    ids=[]
    for dark in [False,True]:
        ids+=sorted(i for i,v in meta.items() if v['unseen_deck_pair'] and v['night']==dark)[:3]
    assert len(ids)==6
    effects={}
    for key in 'rh':
        folder=OUT/'games'/('home-zombie-'+key+'-candidate')
        matches=read(folder/'summary.json')['matches']
        ref={i:dict(match=matches[i],trace=str(folder/'matches'/(i+'.jsonl'))) for i in ids}
        trial=group('home-hint-'+key,ids,MODELS[key],BASE,altered)
        effects[key]=report_comparison('blind','zombie-'+key,'zombie',ref,trial,MODELS[key],BASE,altered,HOME)
    write(root/'result.json',dict(effects=effects,ids=ids,original=sha(model),ablated=sha(altered),
          masked_columns=cols,note='Removed direct use of suggested card, waiting, rally and command flags in both the residual and hidden branches. Original controller clock and auxiliary routines retained. Diagnostic only.'))

