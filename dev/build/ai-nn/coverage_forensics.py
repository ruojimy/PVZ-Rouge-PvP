"""Replay the shared validation timeout 106 with each old/new single seat."""
import gzip
import hashlib
import json
import shutil
from coverage_study import OUT, BIN, H, OLD_MODEL, SIDES, read, write, sha, cmd
import sys

def investigate():
    scenarios=OUT/'plain';root=OUT/'case-106';root.mkdir(exist_ok=True)
    report={}
    for side in SIDES:
        data={}
        for char,model in [('o',OLD_MODEL),('n',OUT/'model/model.json')]:
            arm=char+'r' if side=='plant' else 'r'+char
            out=root/(arm+'.jsonl');archive=root/(arm+'.jsonl.gz')
            assert not archive.exists()
            cmd(BIN/'headless_match.exe','--corpus',scenarios,'--id','106','--out',out,'--planner','nn','--nn-seat',side,'--model',model,'--control-hz','15','--limit-seconds','600','--telemetry')
            rows=[json.loads(line) for line in out.read_bytes().splitlines()]
            original=read(OUT/'validation'/arm/'summary.json')['matches']['106']
            assert rows[-1]['log_sha256']==original['log_sha256'] and rows[-1]['time']==original['time']
            data[char]=[r for r in rows if r['type']=='plan' and r['seat']==side]
            digest=sha(out)
            with out.open('rb') as f,gzip.open(archive,'wb',compresslevel=3) as z:shutil.copyfileobj(f,z)
            with gzip.open(archive,'rb') as z:assert hashlib.file_digest(z,'sha256').hexdigest()==digest
            write(root/(arm+'.json'),dict(original_sha256=digest,archive_sha256=sha(archive),validation=original))
            out.unlink()
        for before,after in zip(data['o'],data['n']):
            assert before['tick']==after['tick'] and before['input']==after['input'] and before['memory']==after['memory']
            if before['plan']!=after['plan']:
                diff={k:[v,after['plan'][k]] for k,v in before['plan'].items() if v!=after['plan'][k]}
                report[side]=dict(tick=before['tick'],time=before['input']['time'],resource=before['input']['me']['resource'],changes=diff,matched_input_and_memory=True)
                break
        assert side in report
    write(root/'first-divergence.json',report)
if __name__=='__main__':investigate()
