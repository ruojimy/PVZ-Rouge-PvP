"""Confirm summary-only training exports the existing native policy format."""
import sys
import numpy as np
import torch
from overnight_common import *
from overnight_train import initialize, export
from night_supplement_train import SummaryNetwork

torch.set_num_threads(1);torch.manual_seed(181118)
doc=read(OLD/'training-1/selected/model.json');full=initialize(doc,0,False)
with torch.no_grad():full.body.weight[:,28:].zero_()
summary=SummaryNetwork(16+len(doc['behaviors']));summary.load_state_dict(full.state_dict())
u=16+len(doc['behaviors']);g=torch.rand(6,28);own=torch.rand(6,5,u);enemy=torch.rand(6,7,u)
om=torch.ones(6,5,dtype=torch.bool);em=torch.ones(6,7,dtype=torch.bool)
torch.testing.assert_close(full(g,own,enemy,om,em),summary(g,own,enemy,om,em),rtol=1e-5,atol=1e-6)
summary(g,own,enemy,om,em).square().sum().backward()
assert summary.unit.weight.grad is None
assert not torch.count_nonzero(summary.body.weight.grad[:,28:])
with np.load(B/'data/validation.npz',allow_pickle=False) as f:header=json.loads(str(f['header']))
out=B/'supplement-contract';export(summary,header,out,False,dict(structural_fixture=True,summary_only=True))
command('supp-summary-contract',[BIN/'neural_contract.exe',out/'model.json'])
command('supp-summary-forward',[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe',
    '--model',out/'model.json','--checkpoint',out/'selected.pt','--out',out/'forward',OLD/'development-r22/matches/010.jsonl'])
write(out/'contract.json',dict(passed=True,unused_unit_parameters_have_no_gradient=True,unused_pool_columns_have_zero_gradient=True,
    native_forward_verified=True,feature_version=2,policy_version=2))
print('summary-only training/native contract passed')
