"""Trainable neutral residual initialization; not a reward-trained policy.

Keep the learned unit/body encoder, reset EVERY output weight, and bias only
neutral correction classes. Argmax actions are exactly r22, including goal 11.
Unlike the all-zero identity fixture, this encoder can receive learning signals.
The checkpoint deliberately uses residual_state_dict, so the absolute-label
train.py cannot silently consume it as an imitation checkpoint.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import torch
from study_train import from_export


def norm(tensor):
    return float(tensor.norm()) if tensor is not None else 0.0


def gradients(model, x, labels):
    model.zero_grad(set_to_none=True)
    loss = torch.nn.functional.cross_entropy(model(*x)[:, :11], labels)
    loss.backward()
    return dict(loss=float(loss.detach()), **{name:norm(parameter.grad) for name,parameter in model.named_parameters()})


ap=argparse.ArgumentParser()
ap.add_argument('--backbone',type=Path,required=True)
ap.add_argument('--features',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args()
assert not args.out.exists(), 'Use a new output directory'
torch.set_num_threads(2)
doc,model=from_export(args.backbone)
assert not doc.get('residual'), 'Backbone must be a validated absolute model'
with torch.no_grad():
    model.heads.weight.zero_();model.heads.bias.zero_()
    for index in (5,11,18):model.heads.bias[index]=1.0
initial=copy.deepcopy(model.state_dict())
doc['residual']=True
doc['enabled_heads']=[True,True,True,False]
doc['heads']={'weight':model.heads.weight.detach().tolist(),'bias':model.heads.bias.detach().tolist()}
doc['initialization']='trained feature encoder with neutral residual output head; no reward optimization performed'
doc['backbone_sha256']=hashlib.sha256(args.backbone.read_bytes()).hexdigest()
# Do not carry absolute-policy training selection metadata onto a new policy semantic.
doc.pop('study_spec',None)

from train import collate
rows=[]
with args.features.open(encoding='utf-8') as source:
    header=json.loads(next(source))
    assert all(header[k]==doc[k] for k in ('catalog_hash','rules_hash','behaviors','sim_fingerprint'))
    for line in source:
        row=json.loads(line)
        if row['seat']!='plant' or row.get('aug'):continue
        row['g']=torch.tensor(row['x']['global'],dtype=torch.float32)
        row['y']=torch.tensor(row['y'],dtype=torch.long);row['plant']=True
        for key in ('own','enemy'):
            a=row['x'][key];row[key+'_count']=len(a)
            row[key]=torch.tensor(a or [[0.0]*(16+len(doc['behaviors']))],dtype=torch.float32)
        rows.append(row)
        if len(rows)==64:break
assert len(rows)>=2
x,_,_=collate(rows)
labels=torch.tensor([4 if i%2 else 6 for i in range(len(rows))])
with torch.no_grad():
    predictions=model(*x)
    assert torch.all(predictions[:,:11].argmax(1)==5)
    assert torch.all(predictions[:,11:13].argmax(1)==0)
    assert torch.all(predictions[:,13:24].argmax(1)==5)

dead=copy.deepcopy(model)
with torch.no_grad():
    for parameter in dead.parameters():parameter.zero_()
    for index in (5,11,18):dead.heads.bias[index]=1.0
dead_grad=gradients(dead,x,labels)
first=gradients(model,x,labels)
optimizer=torch.optim.SGD(model.parameters(),lr=0.001)
optimizer.step()
second=gradients(model,x,labels)
assert dead_grad['unit.weight']==dead_grad['body.weight']==dead_grad['heads.weight']==0.0
assert first['heads.weight']>0 and second['body.weight']>0 and second['unit.weight']>0
# The gradient probe above is synthetic, not actual reinforcement learning.
# Restore the neutral seed before saving anything deployable.
model.load_state_dict(initial)
args.out.mkdir(parents=True)
(args.out/'model.json').write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),'utf-8')
torch.save(dict(format='pvz-residual-seed-checkpoint-1',residual_state_dict=initial,
    policy_semantics='r22-residual',feature_header={k:header[k] for k in ('catalog_hash','rules_hash','behaviors','sim_fingerprint')},
    spec=dict(embedding=doc['embedding'],hidden=doc['hidden']),backbone_sha256=doc['backbone_sha256']),args.out/'residual-seed.pt')
result=dict(passed=True,samples=len(rows),neutral_actions_verified=True,
    all_zero_fixture_gradients=dead_grad,trained_encoder_first_step=first,trained_encoder_second_step=second,
    seed_restored_after_probe=True,reward_training_completed=False,
    note='Synthetic alternating correction targets test gradient flow only. This is still the r22 identity policy.')
(args.out/'initialization-contract.json').write_text(json.dumps(result,indent=2),'utf-8')
print(json.dumps(result))
