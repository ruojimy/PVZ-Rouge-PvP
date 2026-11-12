"""Verify current plant/content evidence; keep all full-product gates closed."""
import argparse
from datetime import datetime,timezone
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
from verify_android_components import host_path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'
PREVIOUS=ROOT/'test_results/typed72-20261104'


def read(p):return json.loads(p.read_text(encoding='utf8'))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True)
    ap.add_argument('--bundle',default='plant-content-regression');ap.add_argument('--audit',default='plant-content-audit')
    ap.add_argument('--negative',nargs='+',default=['plant-content-negative','plant-projectile-negative','plant-target-negative','plant-hero-negative'])
    ap.add_argument('--android-build',nargs='*',default=[]);ap.add_argument('--android-verification')
    a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);errors=[]
    bundle=RUN/a.bundle;regression=read(bundle/'summary.json');has_doom='release-doom' in regression['results'];has_chili='release-chili' in regression['results'];has_death='release-death' in regression['results'];has_registry='release-registry' in regression['results']
    if not regression['passed'] or len(regression['results'])!=(28 if has_registry else 26 if has_death else 22 if has_chili else 20 if has_doom else 18):errors.append('component regression failed/incomplete')
    for path,digest in read(bundle/'pinned.json').items():
        if sha(Path(path))!=digest:errors.append('regression drift '+path)
    for name,item in regression['results'].items():
        evidence=Path(item['evidence']);r=read(evidence)
        if not item['passed'] or not r['passed'] or r['changed_inputs'] or sha(evidence)!=item['sha256']:errors.append('invalid component '+name)
        for path,digest in read(evidence.parent/'pinned.json').items():
            if sha(Path(path))!=digest:errors.append('component drift '+name+'/'+path)
    controls=[]
    for folder in a.negative:
        path=RUN/folder/'summary.json';n=read(path)
        if not n['passed'] or n['original_source_drift']:errors.append('negative failed '+folder)
        for m in n['mutations']:
            if sha(Path(m['original']))!=m['original_sha256']:errors.append('negative original drift '+m['original'])
            if sha(Path(m['mutant']))!=m['mutant_sha256']:errors.append('negative mutant drift '+m['mutant'])
        controls.append(dict(path=str(path),sha256=sha(path),results=[{k:v for k,v in r.items() if k!='targeted_failures'} for r in n['results']]))
    audit_path=RUN/a.audit/'audit.json';audit=read(audit_path)
    if not audit['passed']:errors.append('dependency audit failed')
    for path,digest in audit['local_dependencies'].items():
        if sha(Path(path))!=digest:errors.append('audit drift '+path)
    mappings=[]
    for name in ('hero','target','projectile','plant')+(('doom',) if has_doom else ())+(('chili',) if has_chili else ())+(('death',) if has_death else ())+(('registry',) if has_registry else ()):
        path=ROOT/('docs/coverage/typed72-'+name+'-chain.json');m=read(path)
        for source,digest in m['implementation'].items():
            if sha(Path(source))!=digest:errors.append('mapping drift '+source)
        mappings.append(dict(path=str(path),sha256=sha(path)))
    changed=[];unexpected=[]
    for relative,item in read(PREVIOUS/'continuation-baseline/manifest.json')['files'].items():
        p=ROOT/relative
        if not p.exists() or sha(p)!=item['sha256']:
            changed.append(relative)
            if relative!='README.md' and not relative.startswith(('src/sim/typed/','tools/typed72/','docs/coverage/typed72-')):unexpected.append(relative)
    if unexpected:errors.append('unexpected production source drift')
    android=[];android_comparison=None
    for folder in a.android_build:
        path=RUN/folder/'summary.json';r=read(path)
        if not r['passed'] or r['input_drift']:errors.append('Android component build failed '+folder)
        for source,digest in read(path.parent/'pinned.json').items():
            if sha(host_path(source))!=digest:errors.append('Android build drift '+source)
        for source,item in r['artifacts'].items():
            if sha(host_path(source))!=item['sha256']:errors.append('Android artifact drift '+source)
        android.append(dict(path=str(path),sha256=sha(path),abi=r['abi'],device_execution=r['device_execution']))
    if a.android_verification:
        path=RUN/a.android_verification/'summary.json';r=read(path)
        if not r['passed'] or r['input_drift']:errors.append('Android differential failed')
        for source,digest in read(path.parent/'pinned.json').items():
            if sha(Path(source))!=digest:errors.append('Android differential drift '+source)
        android_comparison=dict(path=str(path),sha256=sha(path),emulator_only=r['emulator_only'],physical_device_tested=r['physical_device_tested'],results=r['results'])
    report=dict(schema=9,created_utc=datetime.now(timezone.utc).isoformat(),status='incomplete',goal_status='active',checkpoint_verification_passed=not errors,
        release_ready=False,pure_typed_game_delivered=False,production_backend='legacy V',full_battle_supported=False,full_same_rule_battle_comparison=False,
        original_full_suite_rerun=False,product_performance_measured=False,PC_typed_game_built=False,APK_typed_game_built=False,
        previous_checkpoint=str(RUN/'checkpoint-registry-chain/status.json') if has_registry and a.android_build else str(RUN/'checkpoint-death-chain/status.json') if has_registry else str(RUN/'checkpoint-chili-chain-v2/status.json') if has_death else str(RUN/'checkpoint-doom-chain/status.json') if has_chili else str(RUN/'checkpoint-plant-chain/status.json') if has_doom else str(PREVIOUS/'checkpoint-projectile-chain/status.json'),
        implemented=['Original five stage kernels','Hero contexts, damage/budgets/status and last stand','Unit protection, target packets/armor/ash dispatch',
            'Raw damage wrappers, knockback and death selector; synchronous sourced composition verified separately' if has_death else 'Raw damage wrappers, knockback and death selector; full sourced death composition pending','All original zombie constructor branches; patch/PvP composition pending',
            'Entity-owned source metadata, synchronous birth tagging and stable retained identity','Live entity list replacement/append semantics and batch handle reclamation',
            'Projectile flight limits, fire-form reset, basketball collision, head geometry and melon/fire splash','One typed event journal preserving cross-system emission order',
            'Original plant constructors, pumpkin-aware lookup, clear markers, terrain destruction and exact PvP bedrock guard',
            'Authoritative plant and tile records; physics, particle and flood overloads can read terrain directly without whole-map conversion',
            'Chili lane/hint and actual gravebuster terrain/plant bodies with callback replacement/exception semantics',
            'NativeContent point, plant/unit/hero damage and plant/hero swept collision; actual content phase and hit kind']+
            (['Actual doom PvP target selection, plant kill, visuals, hero knock and block destruction'] if has_doom else [])+
            (['Actual chili ground snap, hints, player launch/guard, plant/unit damage, 15-segment spawn and scan',
                'Stable typed record identities and independently retained hit-list identity; null-list exception scope preserves continued enemy scanning'] if has_chili else [])+
            (['Actual sourced death composition, eight sourced hooks, spawn retagging, owner hero launch and 60-Hz doom timer',
                'Default sourced fast paths and full contexts; live numeric selector re-resolution and retained target across roster replacement'] if has_death else [])+
            (['Ordered native object registry retains authoritative bodies; key replacement preserves order and reinsert appends',
                'Actual omitted-target collection by grave/barrel HP and duel/duo/PvE/coop seats, composed with synchronous doom deaths'] if has_registry else []),
        verification=regression['results'],negative_controls=controls,dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),source_maps=mappings,
        android_component_builds=android,android_component_comparison=android_comparison,
        errors=errors,changed_from_continuation_baseline=changed,unexpected_source_drift=unexpected,
        source_files={str(p.relative_to(ROOT)):sha(p) for folder in ('src/sim/typed','tools/typed72') for p in (ROOT/folder).glob('*.*') if p.is_file()},
        next_work=['Complete bonus scheduler, thirteen remaining sourced hooks and production admission/registration/cleanup callers.' if has_registry else 'Complete bonus scheduler, thirteen remaining sourced hooks and actual extra-target collector.' if has_death else 'Compose exact sourced PvP death wrappers, spawn retagging, owner hero launch, auto timers and actual extra-target collector.' if has_chili else 'Implement remaining chili effects and auto timers; compose exact sourced PvP death wrappers and actual extra-target collector.' if has_doom else 'Implement actual chili/doom effects; compose exact sourced PvP death wrappers, including the implemented grave bodies.',
            'Compose patch/PvP constructor admission/registration and complete HeroProxy fields; import actual atlas/catalog.',
            'Complete entity motion/torch/zombie-pea/flying-projectile phases, ordinary zombie/pea/hero tick and rendering.',
            'Complete remaining mechanics and typed AI/network/spectator/replay consumers.',
            'Close old full-suite and source/branch gates; independent whole battles; formal PC/Android performance and final products.'],
        preserved_failures=['Previous checkpoint retains historical oracle-harness failures and all failing negative controls.',
            'Current independently compiled faults retain original failed comparisons; no new waivers.']+
            (['chili-initial and chili-fixture-fixed retain two rejected fixture schemas; chili-expanded-initial retains the 24 null-hit-list exception-scope mismatches fixed in chili-null-fixed.',
                'checkpoint-chili-chain retains rejected reuse of the older terrain negative-control hash; current checkpoint requires freshly compiled terrain controls.'] if has_chili else [])+
            (['death-initial retains incorrect 250-Hz auto-age mismatches; corrected to the literal 60-Hz clock.',
                'death-clock-fixed retains uncaught fixture operations; fixed inputs preserve the original failure evidence.',
                'death-negative retains the uncaught fast_hint_sync_order mutation; death-regression-v2 strengthens cached-proxy terrain inputs and death-negative-v2 catches it.'] if has_death else [])+
            (['registry-initial retains the oracle held-state fixture collision; registry-fixture-fixed separates held objects from held terrain.',
                'registry-negative retains rejected missing_orphans attribution: 80 raw failures occurred in composed target scopes, outside its incorrectly selected order-case prefix; registry-negative-v2 verifies the correct targeted cases.'] if has_registry else [])+
            (['registry-android-x86_64 retains the NDK r25 missing <numbers> compile failure; its replacement uses the exact binary64 math.pi constant.'] if a.android_build else []),
        warning='Engineering checkpoint only. Full pure typed PvP72 is not delivered; no missing product gate is waived.')
    if (RUN/'status.json').exists():shutil.copy2(str(RUN/'status.json'),str(out/'previous-status.json'))
    (out/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');shutil.copy2(str(out/'status.json'),str(RUN/'status.json'))
    print(json.dumps(dict(checkpoint_verification_passed=not errors,goal_status='active',release_ready=False,errors=errors)));return 0 if not errors else 1


if __name__=='__main__':sys.exit(main())
