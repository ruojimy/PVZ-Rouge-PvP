"""Exact null-signal control for the 12-opening subset. Retain the original frozen control."""
import sys
import torch
import numpy as np
from coverage_study import OUT,H,BIN,OLD,SIDES,cmd,read,write,sha,run_group
from coverage_fit import readout
def prepare():
    source=OUT/'controls/twelve-both';root=OUT/'zero-control'
    model=read(source/'model.json');stats=read(source/'fit.json')
    for side,offset,classes in [('plant',0,12),('zombie',14,11)]:
        old=stats[side];assert old['positive_rows']==0
        coef,report=readout([(np.zeros((1,28)),np.zeros((1,classes)),np.zeros(1),np.zeros(1,dtype=bool),np.ones(1))])
        assert not coef.any()
        report['samples']=old['samples']; stats[side]=report
        for i in range(classes):model['heads']['weight'][offset+i][-28:]=coef[i].tolist()
    write(root/'model.json',model);write(root/'fit.json',stats)
    st={k+'.'+v:torch.tensor(model[k][v],dtype=torch.double) for k in ('unit','body','heads') for v in ('weight','bias')}
    torch.save(dict(state_dict=st),root/'selected.pt')
    cmd(BIN/'neural_contract.exe',root/'model.json')
    cmd(sys.executable,H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',root/'model.json','--checkpoint',root/'selected.pt','--out',root/'verify',OLD/'development-r22/matches/010.jsonl')
    assert read(root/'verify/report.json')['passed']
    write(OUT/'zero-control-amendment.json',dict(original_control_sha256=sha(source/'model.json'),corrected_model_sha256=sha(root/'model.json'),main_model_sha256=sha(OUT/'model/model.json'),live_source_sha256={p.name:sha(p) for p in H.glob('coverage_*.py')},reason='No positive pairs on 12-opening control; Adam roundoff shifted tied argmax classes even without supervision. Preserve frozen experiment and separately verify exact null at 48 validation games.'))
def parity():
    model=OUT/'zero-control/model.json'
    assert sha(model)==read(OUT/'zero-control-amendment.json')['corrected_model_sha256']
    for seat in SIDES:
        folder=run_group('neutral-parity',seat,model if seat=='plant' else None,model if seat=='zombie' else None,ids=read(OUT/'plan.json')['splits']['validation'])
        candidate=read(folder/'summary.json')['matches']
        ref=read(OUT/'validation'/('or' if seat=='plant' else 'ro')/'summary.json')['matches']
        assert all(ref[k]['log_sha256']==m['log_sha256'] for k,m in candidate.items())
if __name__=='__main__':
    {'prepare':prepare,'parity':parity}[sys.argv[1]]()
