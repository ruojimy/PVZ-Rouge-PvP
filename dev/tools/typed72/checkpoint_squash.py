"""Verify the current squash checkpoint before continuing migration."""
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
    out=RUN/'checkpoint-squash-chain';out.mkdir(exist_ok=False)
    previous=RUN/'checkpoint-fume-chain/status.json';s=read(previous)
    r=read(RUN/'squash-regression/summary.json');n=read(RUN/'squash-negative-accepted/summary.json');a=read(RUN/'squash-audit/audit.json')
    assert r['passed'] and len(r['results'])==40 and n['passed'] and len(n['results'])==16 and a['passed']
    for path,digest in read(RUN/'squash-regression/pinned.json').items():assert sha(Path(path))==digest,path
    for key,value in r['results'].items():
        path=Path(value['evidence']);assert sha(path)==value['sha256'] and value['passed']
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for value in n['results']:
        assert value['caught'] and not read(Path(value['evidence']))['changed_inputs']
    s.update(schema=16,created_utc=datetime.now(timezone.utc).isoformat(),previous_checkpoint=str(previous),verification=r['results'])
    s['dependency_audit']=dict(path=str(RUN/'squash-audit/audit.json'),sha256=sha(RUN/'squash-audit/audit.json'),report=a)
    s['historical_negative_controls']+=s['negative_controls']
    s['negative_controls']=[dict(path=str(RUN/'squash-negative-accepted/summary.json'),sha256=sha(RUN/'squash-negative-accepted/summary.json'),results=n['results'])]
    for m in s['source_maps']:
        path=Path(m['path']);dest=out/'predecessor-maps'/path.name;dest.parent.mkdir(exist_ok=True)
        shutil.copy2(path,dest);m['frozen_path']=str(dest);s['historical_source_maps'].append(m)
    path=ROOT/'docs/coverage/typed72-squash-chain.json';mapping=read(path)
    assert len(mapping['entries'])==38 and not mapping['full_product_acceptance']
    for file,digest in mapping['implementation'].items():assert sha(Path(file))==digest,file
    s.setdefault('preserved_failures',[]).append(dict(path=str(RUN/'squash-initial/summary.json'),sha256=sha(RUN/'squash-initial/summary.json'),reason='Initial fixture comparison required explicit tuple-to-JSON-array normalization and a missing squash-event test projection. Fixed adapters before broad regression.'))
    s['source_maps']=[dict(path=str(path),sha256=sha(path))]
    s['source_files']={str(path.relative_to(ROOT)):sha(path) for folder in ('src/sim/typed','tools/typed72') for path in (ROOT/folder).glob('*.*') if path.is_file()}
    s['implemented']+=['Native squash and shared ballistic target/lead/lock chain, captured births, sourced update/spawn/hit, legacy and damage fallbacks, once-only landing timing, and actual PvP66 pressure splash']
    s['checkpoint_scope']='Current 40 positive component runs, sixteen squash/ballistic faults and local dependency audit. Prior fault families, source maps and Android checks remain historical.'
    s['next_work']=['Migrate the zombie-pea chain, including latest PvP shotgun and hero wrappers.',
        'Complete other three sourced hooks, bonus scheduling and authoritative plant/unit/entity/hero loops.',
        'Complete typed production entry, AI/network/spectators/replay, old full suite and whole battles, current Android and formal performance/products.']
    (out/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(verified_runs=40,negative_faults=16,full_product=False)))
if __name__=='__main__':main()
