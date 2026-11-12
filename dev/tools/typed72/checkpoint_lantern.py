"""Verify the current lantern checkpoint before continuing migration."""
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
    out=RUN/'checkpoint-lantern-chain';out.mkdir(exist_ok=False)
    previous=RUN/'checkpoint-wind-chain/status.json';s=read(previous)
    r=read(RUN/'lantern-regression/summary.json');n=read(RUN/'lantern-negative/summary.json');a=read(RUN/'lantern-audit/audit.json')
    assert r['passed'] and len(r['results'])==34 and n['passed'] and len(n['results'])==6 and a['passed']
    for path,digest in read(RUN/'lantern-regression/pinned.json').items():assert sha(Path(path))==digest,path
    for key,value in r['results'].items():
        path=Path(value['evidence']);assert sha(path)==value['sha256'] and value['passed']
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for value in n['results']:
        assert value['caught'] and not read(Path(value['evidence']))['changed_inputs']
    s.update(schema=13,created_utc=datetime.now(timezone.utc).isoformat(),previous_checkpoint=str(previous),verification=r['results'])
    s['dependency_audit']=dict(path=str(RUN/'lantern-audit/audit.json'),sha256=sha(RUN/'lantern-audit/audit.json'),report=a)
    s['historical_negative_controls']+=s['negative_controls']
    s['negative_controls']=[dict(path=str(RUN/'lantern-negative/summary.json'),sha256=sha(RUN/'lantern-negative/summary.json'),results=n['results'])]
    for m in s['source_maps']:
        path=Path(m['path']);dest=out/'predecessor-maps'/path.name;dest.parent.mkdir(exist_ok=True)
        shutil.copy2(path,dest);m['frozen_path']=str(dest);s['historical_source_maps'].append(m)
    path=ROOT/'docs/coverage/typed72-lantern-chain.json';mapping=read(path)
    assert len(mapping['entries'])==12 and not mapping['full_product_acceptance']
    for file,digest in mapping['implementation'].items():assert sha(Path(file))==digest,file
    s['source_maps']=[dict(path=str(path),sha256=sha(path))]
    s['source_files']={str(path.relative_to(ROOT)):sha(path) for folder in ('src/sim/typed','tools/typed72') for path in (ROOT/folder).glob('*.*') if path.is_file()}
    s['implemented']+=['Actual native maximum-HP tracking, plant/unit healing, proxy increase rejection, light-therapy visual RNG and callbacks, sourced lantern update and native charmed-healing pulses']
    s['checkpoint_scope']='Current 34 positive component runs, six new healing faults and local dependency audit. Prior fault families, source maps and Android checks remain historical.'
    s['next_work']=['Migrate the umbrella, gold-magnet and fumeshroom chains, including latest PvP wrappers.',
        'Complete other ten sourced hooks, bonus scheduling and authoritative plant/unit/entity/hero loops.',
        'Complete typed production entry, AI/network/spectators/replay, old full suite and whole battles, current Android and formal performance/products.']
    (out/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(verified_runs=34,negative_faults=6,full_product=False)))
if __name__=='__main__':main()
