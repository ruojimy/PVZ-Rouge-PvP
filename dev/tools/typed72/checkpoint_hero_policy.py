"""Record a resumable checkpoint without promoting stage proofs to a product."""
import argparse
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261104'


def read(path):return json.loads(path.read_text(encoding='utf8'))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    obligations=[
        ('original_stages','continuation-regression',('damage.cpp','shooter.cpp','flood.cpp','flood.h','physics.cpp','particles.cpp','state.h')),
        ('hero_release','heroes-owner-presence',('hero.h','hero.cpp','state.h','particles.cpp')),
        ('hero_asan','heroes-owner-presence-asan',('hero.h','hero.cpp','state.h','particles.cpp')),
        ('protection_release','protection-release',('protection.h','protection.cpp','hero.h','hero.cpp','state.h')),
        ('protection_asan','protection-asan',('protection.h','protection.cpp','hero.h','hero.cpp','state.h')),
    ]
    verified={};errors=[]
    for name,folder,files in obligations:
        path=RUN/folder;r=read(path/'summary.json');pinned=read(path/'pinned.json')
        if not r['passed'] or r['changed_inputs']:errors.append('unpassed or drifted run: '+name)
        for filename in files:
            source=ROOT/'src/sim/typed'/filename
            if pinned.get(str(source))!=sha(source):errors.append('changed stage source: '+name+'/'+filename)
        verified[name]=dict(path=str(path/'summary.json'),sha256=sha(path/'summary.json'),cases=r['cases'],passed_cases=r['passed_cases'],
                            steps=r.get('compared_steps',r.get('compared_stage_steps')))
    negative=read(RUN/'hero-protection-negative/summary.json');audit=read(RUN/'hero-policy-audit/audit.json')
    if not negative['passed'] or not audit['passed']:errors.append('negative control or dependency audit failed')
    for source,expected in audit['local_dependencies'].items():
        if sha(Path(source))!=expected:errors.append('audit source changed: '+source)
    baseline=read(RUN/'continuation-baseline/manifest.json');changed=[];unexpected=[]
    for relative,item in baseline['files'].items():
        p=ROOT/relative
        if not p.exists() or sha(p)!=item['sha256']:
            changed.append(relative)
            if relative!='README.md' and not relative.startswith(('src/sim/typed/','tools/typed72/','docs/coverage/typed72-')):unexpected.append(relative)
    if unexpected:errors.append('unexpected baseline drift')
    report=dict(schema=2,created_utc=datetime.now(timezone.utc).isoformat(),status='incomplete',goal_status='active',
        checkpoint_verification_passed=not errors,release_ready=False,pure_typed_game_delivered=False,
        production_backend='legacy V',full_battle_supported=False,full_same_rule_battle_comparison=False,
        original_full_suite_rerun=False,product_performance_measured=False,PC_typed_game_built=False,APK_typed_game_built=False,
        implemented=['Original five stage kernels','Hero target contexts, damage/budgets, proxy HP/status, source precedence and last stand',
                     'Numeric unit protection and zombie secret damage/relic policies'],
        verification=verified,negative_controls=negative['results'],dependency_audit=str(RUN/'hero-policy-audit/audit.json'),
        errors=errors,changed_from_continuation_baseline=changed,unexpected_source_drift=unexpected,
        source_files={str(p.relative_to(ROOT)):sha(p) for folder in ('src/sim/typed','tools/typed72') for p in (ROOT/folder).glob('*.*') if p.is_file()},
        next_work=[
            'Preserve NativeTargets._unit_damage packets and source wrapper installation order when composing typed damage.',
            'Migrate original patch wrap_damage_zombie/wrap_surface_damage_zombie/wrap_ash_zombie, including death effects; no call-through to V.',
            'Migrate projectile tag/instant-attack tokens, full proxy shape, target lists and armor drop metadata.',
            'Build the authoritative typed world and complete E1 zombie/pea/hero tick, including hero input/environment/effects.',
            'Expand all current PvP72 mechanics, AI, transport, spectator/replay; run full source/branch/old-suite/battle/performance/product gates.'],
        warning='This is a resumable engineering checkpoint, not a delivered PvP72 typed product. No unmet gate is waived.')
    if (RUN/'status.json').exists():shutil.copy2(str(RUN/'status.json'),str(out/'previous-status.json'))
    (out/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(str(out/'status.json'),str(RUN/'status.json'))
    print(json.dumps(dict(checkpoint_verification_passed=not errors,goal_status='active',release_ready=False,errors=errors)))
    return 0 if not errors else 1


if __name__=='__main__':sys.exit(main())
