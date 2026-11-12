"""Save current exact evidence; all whole-product gates remain explicitly open."""
import argparse
from datetime import datetime,timezone
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261104'


def read(p):return json.loads(p.read_text(encoding='utf8'))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);errors=[]
    bundle=RUN/'target-patch-regression';regression=read(bundle/'summary.json')
    if not regression['passed']:errors.append('component regression failed')
    for path,digest in read(bundle/'pinned.json').items():
        if sha(Path(path))!=digest:errors.append('regression source drift: '+path)
    for name,item in regression['results'].items():
        evidence=Path(item['evidence']);r=read(evidence)
        if not item['passed'] or not r['passed'] or r['changed_inputs'] or sha(evidence)!=item['sha256']:errors.append('invalid component evidence: '+name)
        for path,digest in read(evidence.parent/'pinned.json').items():
            if sha(Path(path))!=digest:errors.append('component input drift: '+name+'/'+path)
    controls=[]
    for folder in ('target-patch-negative','hero-policy-negative-current'):
        path=RUN/folder/'summary.json';n=read(path)
        if not n['passed'] or n['original_source_drift']:errors.append('negative control failed: '+folder)
        for mutation in n['mutations']:
            if sha(Path(mutation['original']))!=mutation['original_sha256']:errors.append('negative original source drift')
        controls.append(dict(path=str(path),sha256=sha(path),results=[{k:v for k,v in r.items() if k!='targeted_failures'} for r in n['results']]))
    audit_path=RUN/'target-patch-audit/audit.json';audit=read(audit_path)
    if not audit['passed']:errors.append('dependency audit failed')
    for path,digest in audit['local_dependencies'].items():
        if sha(Path(path))!=digest:errors.append('audit drift: '+path)
    map_path=ROOT/'docs/coverage/typed72-target-chain.json';mapping=read(map_path)
    for path,digest in mapping['implementation'].items():
        if sha(Path(path))!=digest:errors.append('mapping drift: '+path)
    changed=[];unexpected=[]
    for relative,item in read(RUN/'continuation-baseline/manifest.json')['files'].items():
        p=ROOT/relative
        if not p.exists() or sha(p)!=item['sha256']:
            changed.append(relative)
            if relative!='README.md' and not relative.startswith(('src/sim/typed/','tools/typed72/','docs/coverage/typed72-')):unexpected.append(relative)
    if unexpected:errors.append('unexpected production source drift')
    report=dict(schema=3,created_utc=datetime.now(timezone.utc).isoformat(),status='incomplete',goal_status='active',
        checkpoint_verification_passed=not errors,release_ready=False,pure_typed_game_delivered=False,production_backend='legacy V',
        full_battle_supported=False,full_same_rule_battle_comparison=False,original_full_suite_rerun=False,
        product_performance_measured=False,PC_typed_game_built=False,APK_typed_game_built=False,
        implemented=['Original five stage kernels','Hero contexts, damage/budgets/status and last stand',
            'Typed projectile metadata, attack identities and birth-flight state','Shared authoritative unit records and stable source references',
            'Unit protection and target damage packet/armor/ash dispatch','Original damage patch wrappers, knockback and death selection (effect bodies pending)',
            'All original zombie constructor branches (PvP and patch composition pending)'],
        verification=regression['results'],negative_controls=controls,dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),
        source_map=dict(path=str(map_path),sha256=sha(map_path)),errors=errors,changed_from_continuation_baseline=changed,unexpected_source_drift=unexpected,
        source_files={str(p.relative_to(ROOT)):sha(p) for folder in ('src/sim/typed','tools/typed72') for p in (ROOT/folder).glob('*.*') if p.is_file()},
        next_work=['Complete entity-owned metadata, spawn tagging and synchronous sourced death callbacks.',
            'Implement actual chili/doom/grave terrain, targets and spawn effects; required interfaces are not complete mechanics.',
            'Compose patch/PvP constructor registration and full HeroProxy shape/writes with original constructor.',
            'Finish authoritative world and complete E1 ordinary zombie/pea/hero tick with input, physics and drawing.',
            'Migrate all latest PvP72 mechanics, AI, multiplayer/spectator/replay; close full source/branch/old-suite/battle/performance/product gates.'],
        preserved_failures=['targets-initial: independent shield hook incorrectly disabled with amount hook; fixed and rerun',
            'spawn-initial: oracle omitted builtins; corrected reference environment and rerun',
            'all deliberately mutated negative-control failures'],
        warning='Engineering checkpoint only. The requested pure typed PvP72 product is not finished; no missing gate is waived.')
    if (RUN/'status.json').exists():shutil.copy2(str(RUN/'status.json'),str(out/'previous-status.json'))
    (out/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');shutil.copy2(str(out/'status.json'),str(RUN/'status.json'))
    print(json.dumps(dict(checkpoint_verification_passed=not errors,goal_status='active',release_ready=False,errors=errors)))
    return 0 if not errors else 1


if __name__=='__main__':sys.exit(main())
