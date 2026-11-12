"""Close the unchanged pea checkpoint before integrating the shooting loop."""
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
    previous=RUN/'checkpoint-squash-chain/status.json';s=read(previous)
    regression=RUN/'pea-regression-alias';negative=RUN/'pea-negative-accepted/summary.json'
    r=read(regression/'summary.json');n=read(negative);a=read(RUN/'pea-audit/audit.json')
    assert r['passed'] and len(r['results'])==42 and n['passed'] and len(n['results'])==24 and a['passed']
    for path,digest in read(regression/'pinned.json').items():assert sha(Path(path))==digest,path
    for value in r['results'].values():
        path=Path(value['evidence']);assert sha(path)==value['sha256'] and value['passed']
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for value in n['results']:assert value['caught'] and not read(Path(value['evidence']))['changed_inputs']
    path=ROOT/'docs/coverage/typed72-pea-chain.json';mapping=read(path);assert len(mapping['entries'])==26 and not mapping['full_product_acceptance']
    for file,digest in mapping['implementation'].items():assert sha(Path(file))==digest,file
    out=RUN/'checkpoint-pea-chain';out.mkdir(exist_ok=False)
    s.update(schema=17,created_utc=datetime.now(timezone.utc).isoformat(),previous_checkpoint=str(previous),verification=r['results'])
    s['dependency_audit']=dict(path=str(RUN/'pea-audit/audit.json'),sha256=sha(RUN/'pea-audit/audit.json'),report=a)
    s['historical_negative_controls']+=s['negative_controls'];s['negative_controls']=[dict(path=str(negative),sha256=sha(negative),results=n['results'])]
    for m in s['source_maps']:
        old=Path(m['path']);dest=out/'predecessor-maps'/old.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(old,dest);m['frozen_path']=str(dest);s['historical_source_maps'].append(m)
    s.setdefault('preserved_failures',[]).append(dict(path=str(RUN/'pea-initial/summary.json'),sha256=sha(RUN/'pea-initial/summary.json'),reason='Initial clock adapter only advanced engine time; fixed its global native tick. Surface damage also required a typed installed nested ordinary entry, including exception and active protection-packet semantics.'))
    first_negative=RUN/'pea-negative/summary.json'
    s['preserved_failures'].append(dict(path=str(first_negative),sha256=sha(first_negative),reason='One list-identity fault escaped because replacement and survivors were indistinguishable. An isolated recompile with distinguishable replacement lists failed 16 targeted cases. Other faults retain witnessed failures on unchanged inputs.'))
    s['source_maps']=[dict(path=str(path),sha256=sha(path))]
    s['source_files']={str(p.relative_to(ROOT)):sha(p) for folder in ('src/sim/typed','tools/typed72') for p in (ROOT/folder).glob('*.*') if p.is_file()}
    s['implemented']+=['Native zombie-pea spawn/update/collision/fire/splash and all three sourced wrappers, latest shotgun and hero firing, typed nested ordinary-damage route']
    s['checkpoint_scope']='Current 42 positive component runs, 24 pea faults and dependency audit; prior fault families, source maps and Android checks remain historical.'
    s['next_work']=['Integrate and verify the complete plant-zombie shooting subloop and bonus scheduler.',
        'Complete authoritative plant/unit/entity/hero loops and remaining PvP content, assets and typed production entry.',
        'Complete AI/network/spectators/replay, old full suite and whole battles, current Android and formal performance/products.']
    (out/'status.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(dict(verified_runs=42,negative_faults=24,full_product=False)))
if __name__=='__main__':main()
