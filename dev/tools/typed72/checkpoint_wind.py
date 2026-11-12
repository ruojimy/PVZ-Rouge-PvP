"""Verify the current wind checkpoint before continuing migration."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
    out=RUN/'checkpoint-wind-chain';out.mkdir(exist_ok=False)
    previous=RUN/'checkpoint-aim-chain/status.json';s=read(previous)
    r=read(RUN/'wind-regression-v2/summary.json');n=read(RUN/'wind-negative-v2/summary.json');a=read(RUN/'wind-audit/audit.json')
    assert r['passed'] and len(r['results'])==32 and n['passed'] and len(n['results'])==9 and a['passed']
    for path,digest in read(RUN/'wind-regression-v2/pinned.json').items():assert sha(Path(path))==digest,path
    for key,value in r['results'].items():
        path=Path(value['evidence']);assert sha(path)==value['sha256'] and value['passed']
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for value in n['results']:
        assert value['caught'] and not read(Path(value['evidence']))['changed_inputs']
    s.update(schema=12,created_utc=datetime.now(timezone.utc).isoformat(),previous_checkpoint=str(previous),verification=r['results'])
    s['dependency_audit']=dict(path=str(RUN/'wind-audit/audit.json'),sha256=sha(RUN/'wind-audit/audit.json'),report=a)
    s['historical_negative_controls']+=s['negative_controls']
    s['negative_controls']=[dict(path=str(RUN/'wind-negative-v2/summary.json'),sha256=sha(RUN/'wind-negative-v2/summary.json'),results=n['results'])]
    for m in s['source_maps']:
        path=Path(m['path']);dest=out/'predecessor-maps'/path.name;dest.parent.mkdir(exist_ok=True)
        shutil.copy2(path,dest);m['frozen_path']=str(dest);s['historical_source_maps'].append(m)
    path=ROOT/'docs/coverage/typed72-wind-chain.json';mapping=read(path)
    assert len(mapping['entries'])==17 and not mapping['full_product_acceptance']
    for file,digest in mapping['implementation'].items():assert sha(Path(file))==digest,file
    s['source_maps']=[dict(path=str(path),sha256=sha(path))]
    s['source_files']={str(path.relative_to(ROOT)):sha(path) for folder in ('src/sim/typed','tools/typed72') for path in (ROOT/folder).glob('*.*') if path.is_file()}
    s['implemented']+=['Retainable typed unit/entity position records, preserving native list replacement and alias identity',
        'Actual native wind/update and PvP59 radius/index mapping, PvP56 hidden shots, PvP70 bone/grenade extension; nested callback/restoration and per-frame hero wind']
    s['checkpoint_scope']='Current 32 positive component runs, nine new wind/identity faults and local dependency audit. Prior fault families, maps and Android checks remain historical.'
    s['next_work']=['Integrate drafted lantern healing, shared maximum-HP tracking and native charmed healing, with actual oracle and failure controls.',
        'Continue remaining eleven sourced hooks, bonus scheduler and full authoritative unit/entity/hero/plant loops.',
        'Complete typed game entry, AI/network/spectators/replay, old full suite and whole-battle proof, current Android builds and formal performance/products.']
    (out/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(verified_runs=32,negative_faults=9,full_product=False)))
if __name__=='__main__':main()
