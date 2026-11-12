"""Pin current integrated component evidence without promoting product gates."""
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


def read(path):return json.loads(path.read_text(encoding='utf8'))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);errors=[]
    bundle=RUN/'projectile-event-regression';regression=read(bundle/'summary.json')
    if not regression['passed']:errors.append('component regression failed')
    for path,digest in read(bundle/'pinned.json').items():
        if sha(Path(path))!=digest:errors.append('regression drift '+path)
    for name,item in regression['results'].items():
        evidence=Path(item['evidence']);r=read(evidence)
        if not item['passed'] or not r['passed'] or r['changed_inputs'] or sha(evidence)!=item['sha256']:errors.append('invalid component '+name)
        for path,digest in read(evidence.parent/'pinned.json').items():
            if sha(Path(path))!=digest:errors.append('component drift '+name+'/'+path)
    controls=[]
    for folder in ('projectile-event-negative','target-event-negative','hero-event-negative'):
        path=RUN/folder/'summary.json';n=read(path)
        if not n['passed'] or n['original_source_drift']:errors.append('negative failed '+folder)
        for m in n['mutations']:
            if sha(Path(m['original']))!=m['original_sha256']:errors.append('negative original drift '+m['original'])
        controls.append(dict(path=str(path),sha256=sha(path),results=[{k:v for k,v in r.items() if k!='targeted_failures'} for r in n['results']]))
    audit_path=RUN/'projectile-event-audit/audit.json';audit=read(audit_path)
    if not audit['passed']:errors.append('dependency audit failed')
    for path,digest in audit['local_dependencies'].items():
        if sha(Path(path))!=digest:errors.append('audit drift '+path)
    mappings=[]
    for name in ('hero','target','projectile'):
        path=ROOT/('docs/coverage/typed72-'+name+'-chain.json');m=read(path)
        for source,digest in m['implementation'].items():
            if sha(Path(source))!=digest:errors.append('mapping drift '+source)
        mappings.append(dict(path=str(path),sha256=sha(path)))
    changed=[];unexpected=[]
    for relative,item in read(RUN/'continuation-baseline/manifest.json')['files'].items():
        p=ROOT/relative
        if not p.exists() or sha(p)!=item['sha256']:
            changed.append(relative)
            if relative!='README.md' and not relative.startswith(('src/sim/typed/','tools/typed72/','docs/coverage/typed72-')):unexpected.append(relative)
    if unexpected:errors.append('unexpected production source drift')
    report=dict(schema=4,created_utc=datetime.now(timezone.utc).isoformat(),status='incomplete',goal_status='active',checkpoint_verification_passed=not errors,
        release_ready=False,pure_typed_game_delivered=False,production_backend='legacy V',full_battle_supported=False,full_same_rule_battle_comparison=False,
        original_full_suite_rerun=False,product_performance_measured=False,PC_typed_game_built=False,APK_typed_game_built=False,
        implemented=['Original five stage kernels','Hero contexts, damage/budgets/status and last stand','Unit protection, target packets/armor/ash dispatch',
            'Raw damage wrappers, knockback and death selector; actual effect bodies pending','All original zombie constructor branches; patch/PvP composition pending',
            'Entity-owned source metadata, synchronous birth tagging and stable retained identity','Live entity list replacement/append semantics and batch handle reclamation',
            'Projectile flight limits, fire-form reset, mobile basketball collision, plant-zombie head geometry and melon/fire splash',
            'One typed event journal preserving interleaved hero/relic/basketball/splash order'],
        verification=regression['results'],negative_controls=controls,dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),source_maps=mappings,
        errors=errors,changed_from_continuation_baseline=changed,unexpected_source_drift=unexpected,
        source_files={str(p.relative_to(ROOT)):sha(p) for folder in ('src/sim/typed','tools/typed72') for p in (ROOT/folder).glob('*.*') if p.is_file()},
        next_work=['Implement actual chili/doom/grave terrain, targets and spawn effects; bind exact PvP sourced wrappers.',
            'Compose patch/PvP constructor registration, plant-zombie catalog and complete HeroProxy constructor/writes.',
            'Complete entity motion/torch/zombie-pea/flying-projectile phases; load actual immutable atlas/catalog.',
            'Finish E1 complete ordinary zombie/pea/hero tick, input/physics/drawing on the single authoritative world.',
            'Migrate all current mechanics, AI, multiplayer/spectators/replay; event consumers and transport are still pending.',
            'Close full source/branch and old-suite gates; independent whole-battle comparison; formal PC/Android performance; final products.'],
        preserved_failures=['projectile-impact-initial: oracle emit parameter collided with native event kind keyword; reference harness fixed, all results rerun',
            'Earlier target shield-hook and spawn builtins failures retained','All deliberately mutated negative-control failures retained'],
        warning='Engineering checkpoint only; requested complete pure typed PvP72 is not delivered. No missing gate is waived.')
    if (RUN/'status.json').exists():shutil.copy2(str(RUN/'status.json'),str(out/'previous-status.json'))
    (out/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');shutil.copy2(str(out/'status.json'),str(RUN/'status.json'))
    print(json.dumps(dict(checkpoint_verification_passed=not errors,goal_status='active',release_ready=False,errors=errors)));return 0 if not errors else 1


if __name__=='__main__':sys.exit(main())
