"""State-dependent bounded actor heads over the frozen, trained neural encoder."""
import copy, json
import numpy as np
import torch
from overnight_common import *
from overnight_train import PolicyNetwork, load_cache, initialize, batches

D=B/'residual';NBIN=D/'native-build/Release'
PARENTS={s:Path(v['model']) for s,v in read(B/'selection.json')['best'].items()}

def prepare_calibration():
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    header,rows=load_cache(B/'data/train.npz')
    with np.load(B/'data/validation.npz',allow_pickle=False) as data:held={bytes(x) for x in data['hashes']}
    arrays={};info={}
    for side in ['plant','zombie']:
        unique={}
        for i,r in enumerate(rows):
            if r['plant']==(side=='plant') and r['sample_weight']==1. and r['hash'] not in held:unique.setdefault(r['hash'],i)
        candidates=list(unique.values());rng=np.random.default_rng(181120+(side=='zombie'))
        indices=rng.choice(candidates,min(8192,len(candidates)),replace=False)
        doc=read(PARENTS[side]);assert all(doc[k]==header[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint'])
        model=initialize(doc,0,False).double().eval();activation=[]
        handle=model.body.register_forward_hook(lambda module,inputs,output:activation.append(output.detach().clamp(min=0).numpy().copy()))
        with torch.no_grad():
            for x,_,_,_ in batches([rows[int(i)] for i in indices]):model(*(v.double() for v in x))
        handle.remove();h=np.concatenate(activation);assert np.isfinite(h).all()
        scale=np.maximum(np.sqrt((h*h).mean(0)),.05)
        arrays['h_'+side]=h;arrays['scale_'+side]=scale;arrays['indices_'+side]=indices
        offset=0 if side=='plant' else 14
        weights=np.asarray(doc['heads']['weight']);contrast=(weights[offset+7:offset+11].mean(0)-weights[offset+2:offset+6].mean(0))*scale
        if np.linalg.norm(contrast)<1e-8:contrast=rng.normal(size=len(scale))
        arrays['contrast_'+side]=contrast/np.linalg.norm(contrast)
        info[side]=dict(samples=len(h),unique_canonical_candidates=len(candidates),parent=str(PARENTS[side]),parent_sha256=sha(PARENTS[side]))
    arrays['header']=np.array(json.dumps(header));path=D/'calibration.npz';assert not path.exists()
    np.savez_compressed(path,**arrays)
    write(D/'calibration.json',dict(sides=info,data_sha256=sha(B/'data/train.npz'),validation_hash_filter_sha256=sha(B/'data/validation.npz'),
        calibration_sha256=sha(path),scope='Unique canonical training states only; exclude exact validation feature hashes. No test data.'))
    return info

def calibration(side):
    with np.load(D/'calibration.npz',allow_pickle=False) as f:
        return f['h_'+side],f['scale_'+side],f['contrast_'+side],json.loads(str(f['header']))

def policy_digest(doc):
    p={k:v for k,v in doc.items() if k!='training_source'}
    return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def save_actor(name,side,genes=None,rates=None):
    folder=D/'models'/name;assert not folder.exists();guard()
    doc=copy.deepcopy(read(PARENTS[side]));h,scale,_,header=calibration(side)
    for key in ['mode_hidden','mode_body','mode_output']:doc.pop(key,None)
    width=doc['hidden'];weights=np.zeros((28,width),dtype=np.float32);bias=np.full(28,-1e6,dtype=np.float32)
    bias[[5,12,19,26]]=0.;offset=0 if side=='plant' else 14
    if genes is not None:
        assert len(rates)==2 and any(r>0 for r in rates)
        for i,cls in enumerate([4,6]):
            if not rates[i]:continue
            w=np.asarray(genes[i],dtype=np.float64)/scale;project=h@w
            w=w/max(float(project.std()),.05);project=h@w
            weights[offset+cls]=w.astype(np.float32)
            # Margin avoids exact quantile ties becoming a non-neutral action.
            bias[offset+cls]=np.float32(-np.quantile(project,1-rates[i])-1e-4)
    predicted=(h@weights[offset:offset+(12 if side=='plant' else 11)].T+bias[offset:offset+(12 if side=='plant' else 11)]).argmax(1)
    histogram={str(i-5):int((predicted==i).sum()) for i in [4,5,6]}
    active=1-histogram['0']/len(h)
    if genes is not None:assert .005<=active<=.405, (name,active)
    doc.update(format='pvz-deepset-bounded-residual-1',residual=True,mode_transition=False,
        enabled_heads=[True,False,True,False],heads=dict(weight=weights.tolist(),bias=bias.tolist()),
        training_source=dict(method='bounded neural head outcome search',neutral_initialization=genes is None,side=side,parent=str(PARENTS[side]),parent_sha256=sha(PARENTS[side]),
            mutable_parameters=2*width+2,mode_and_save='r22',max_absolute_strategy_step=1,calibration_sha256=sha(D/'calibration.npz')))
    folder.mkdir(parents=True);write(folder/'model.json',doc)
    net=PolicyNetwork(16+len(doc['behaviors']),0)
    with torch.no_grad():
        for key in ['unit','body','heads']:
            layer=getattr(net,key);layer.weight.copy_(torch.tensor(doc[key]['weight']));layer.bias.copy_(torch.tensor(doc[key]['bias']))
    torch.save(dict(state_dict=net.state_dict(),feature_header=header,spec=dict(embedding=8,hidden=64,feature_version=2,policy_version=2,mode_hidden=0,mode_transition=False)),folder/'selected.pt')
    info=dict(name=name,side=side,model=str(folder/'model.json'),model_sha256=sha(folder/'model.json'),policy_digest=policy_digest(doc),
        calibration_delta_histogram=histogram,calibration_nonzero_rate=active,
        genes=None if genes is None else np.asarray(genes).tolist(),rates=rates,neutral=genes is None)
    write(folder/'actor.json',info);return info
