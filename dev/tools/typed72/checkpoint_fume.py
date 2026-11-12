"""Verify the current fumeshroom checkpoint before continuing migration."""
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
    out=RUN/'checkpoint-fume-chain';out.mkdir(exist_ok=False)
    previous=RUN/'checkpoint-service-chain/status.json';s=read(previous)
    r=read(RUN/'fume-regression-v2/summary.json');n=read(RUN/'fume-negative-v2/summary.json');a=read(RUN/'fume-audit-v2/audit.json')
    assert r['passed'] and len(r['results'])==38 and n['passed'] and len(n['results'])==13 and a['passed']
    for path,digest in read(RUN/'fume-regression-v2/pinned.json').items():assert sha(Path(path))==digest,path
    for key,value in r['results'].items():
        path=Path(value['evidence']);assert sha(path)==value['sha256'] and value['passed']
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for value in n['results']:
        assert value['caught'] and not read(Path(value['evidence']))['changed_inputs']
    s.update(schema=15,created_utc=datetime.now(timezone.utc).isoformat(),previous_checkpoint=str(previous),verification=r['results'])
    s['dependency_audit']=dict(path=str(RUN/'fume-audit-v2/audit.json'),sha256=sha(RUN/'fume-audit-v2/audit.json'),report=a)
    s['historical_negative_controls']+=s['negative_controls']
    s['negative_controls']=[dict(path=str(RUN/'fume-negative-v2/summary.json'),sha256=sha(RUN/'fume-negative-v2/summary.json'),results=n['results'])]
    for m in s['source_maps']:
        path=Path(m['path']);dest=out/'predecessor-maps'/path.name;dest.parent.mkdir(exist_ok=True)
        shutil.copy2(path,dest);m['frozen_path']=str(dest);s['historical_source_maps'].append(m)
    path=ROOT/'docs/coverage/typed72-fume-chain.json';mapping=read(path)
    assert len(mapping['entries'])==26 and not mapping['full_product_acceptance']
    for file,digest in mapping['implementation'].items():assert sha(Path(file))==digest,file
    s.setdefault('preserved_failures',[]).append(dict(path=str(RUN/'fume-initial/summary.json'),sha256=sha(RUN/'fume-initial/summary.json'),reason='Initial test callback omitted the existing player-damage adapter call record; adapter corrected before full regression.'))
    s.setdefault('preserved_failures',[]).append(dict(path=str(RUN/'fume-negative/summary.json'),sha256=sha(RUN/'fume-negative/summary.json'),reason='First negative run had a line-versus-target classification mismatch and an undetected removed-update-context mutant. Added 24 real context fixtures and reran all 13 controls.'))
    s['source_maps']=[dict(path=str(path),sha256=sha(path))]
    s['source_files']={str(path.relative_to(ROOT)):sha(path) for folder in ('src/sim/typed','tools/typed72') for path in (ROOT/folder).glob('*.*') if path.is_file()}
    s['implemented']+=['Actual fumeshroom target/line/pulse chain with producer protection, callback fallbacks, sourced updates, metal stun, native bubble creation and time-based animation']
    s['checkpoint_scope']='Current 38 positive component runs, thirteen fumeshroom faults and local dependency audit. Prior fault families, source maps and Android checks remain historical.'
    s['next_work']=['Migrate the squash and zombie-pea chains, including latest PvP wrappers.',
        'Complete other six sourced hooks, bonus scheduling and authoritative plant/unit/entity/hero loops.',
        'Complete typed production entry, AI/network/spectators/replay, old full suite and whole battles, current Android and formal performance/products.']
    (out/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(verified_runs=38,negative_faults=13,full_product=False)))
if __name__=='__main__':main()
