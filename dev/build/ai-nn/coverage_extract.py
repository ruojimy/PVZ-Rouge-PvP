"""Extract r22 targets and old-network logits from each exact visited state."""
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
from overnight_common import BIN, OLD, read, write, sha
from coverage_guard import OUT

LIFT=OUT/'old-lifted.json'
def lift():
    if LIFT.exists():
        return read(LIFT)
    doc=read(OLD/'warm/old.json')
    assert doc.get('feature_version',1)==1 and doc.get('policy_version',1)==1 and not doc.get('residual')
    doc['body']['weight']=[w[:20]+[0.]*8+w[20:] for w in doc['body']['weight']]
    for field in ['weight','bias']:
        old=doc['heads'][field]
        extra=old[10] if field=='weight' else old[10]-12
        doc['heads'][field]=old[:11]+[extra]+old[11:]
    doc.update(feature_version=2,policy_version=2)
    write(LIFT,doc)
    return doc

def features(src,dst):
    tmp=dst.with_suffix('.tmp.npz')
    args=[str(BIN/'neural_dataset.exe'),'-',str(LIFT),'--relabel','1','--stride','3',str(src)]
    g=[];y=[];logits=[];ticks=[]
    with subprocess.Popen(args,stdout=subprocess.PIPE,encoding='utf-8') as p:
        header=json.loads(next(p.stdout))
        for line in p.stdout:
            row=json.loads(line);g.append(row['x']['global']);y.append(row['y']);logits.append(row['logits']);ticks.append(row['tick'])
        if p.wait(): raise RuntimeError('encoder failed')
    assert len(g)>0 and len(g[0])==28 and len(logits[0])==28
    np.savez_compressed(tmp,g=np.array(g,dtype='f8'),y=np.array(y,dtype='i2'),logits=np.array(logits,dtype='f8'),ticks=np.array(ticks,dtype='i4'))
    os.replace(tmp,dst)

def compact(folder,uid):
    lift()
    raw=folder/'matches'/(uid+'.jsonl')
    archive=folder/'archives'/(uid+'.jsonl.gz')
    cache=folder/'cache'/(uid+'.npz')
    marker=folder/'receipts'/(uid+'.json')
    if marker.exists() and sha(raw)==read(marker)['compact_sha256']: return
    original=read(folder/'summary.json')['matches'][uid]['file_sha256']
    assert sha(raw)==original
    archive.parent.mkdir(exist_ok=True);cache.parent.mkdir(exist_ok=True)
    features(raw,cache)
    with raw.open('rb') as f, gzip.open(archive,'wb',compresslevel=3) as z: shutil.copyfileobj(f,z)
    with gzip.open(archive,'rb') as z: assert hashlib.file_digest(z,'sha256').hexdigest()==original
    with raw.open('rb') as f:
        head=json.loads(next(f));last=b''
        for line in f:last=line
    foot=json.loads(last);assert foot['type']=='result'
    head.update(records=False,original=archive.name)
    tmp=raw.with_suffix('.compact')
    tmp.write_bytes(json.dumps(head,ensure_ascii=False).encode()+b'\n'+last)
    write(marker,dict(raw_sha256=original,archive_sha256=sha(archive),compact_sha256=sha(tmp),cache_sha256=sha(cache),planners=head['planners']))
    os.replace(tmp,raw)
