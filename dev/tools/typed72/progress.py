"""Write an evidence-bound, explicitly incomplete migration checkpoint."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261104'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    release=read(RUN/'stages-final/summary.json')
    sanitizer=read(RUN/'asan-checked/summary.json')
    audit=read(RUN/'audit-final/audit.json')
    negative=read(RUN/'negative-control/differential/summary.json')
    inventory=read(RUN/'inventory/inventory-summary.json')
    baseline=read(RUN/'baseline/manifest.json')
    production=read(RUN/'production-binary-check.json')
    changed=[];missing=[]
    for name,entry in baseline['files'].items():
        p=ROOT/name
        if not p.exists():missing.append(name)
        elif sha(p)!=entry['sha256']:changed.append(name)
    expected={'CMakeLists.txt','android/CMakeLists.txt','README.md'}
    unrelated=[p for p in changed if p not in expected]
    stage_verification=release['passed'] and sanitizer['passed'] and audit['passed']
    negative_detected=not negative['passed'] and negative['process_exit_code']==0 and negative['passed_cases']<negative['cases']
    valid_checkpoint=stage_verification and negative_detected and production['byte_identical'] and not unrelated and not missing
    source_paths=list((ROOT/'src/sim/typed').glob('*.*'))+list((ROOT/'tools/typed72').glob('*.*'))
    evidence_paths=[RUN/'stages-final/summary.json',RUN/'asan-checked/summary.json',
        RUN/'audit-final/audit.json',RUN/'negative-control/differential/summary.json',
        RUN/'negative-control/damage-mutant.cpp',RUN/'inventory/inventory-summary.json',
        RUN/'production-binary-check.json',ROOT/'docs/coverage/typed72-stage-migration.json']
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),
        request='完整保留最新PvP72机制，重建类型化C++权威战斗内核并交付游戏',
        status='incomplete',checkpoint_verification_passed=valid_checkpoint,
        release_ready=False,pure_typed_game_delivered=False,production_backend='legacy V',
        milestone_status={'E0':'partial: freeze/rebuild/inventory done; source closure and full dual-world launch incomplete',
            'E1':'partial: five typed stages verified; no complete zombie/pea/hero battle loop',
            'E2':'not complete','E3':'not run','E4':'not run'},
        implemented=['stable generation handles and order-preserving storage','missing/None/zero field semantics',
            'original ordinary/surface zombie damage','original six-shooter attack block',
            'periodic flood with authoritative typed field and reusable frontier buffers',
            'original particle emitter including RNG, pixel sampling, movement, deletion and draw events',
            'original body collision displacement with periodic/nonperiodic bounds'],
        verification=dict(release_cases=release['cases'],release_stage_steps=release['compared_stage_steps'],
            sanitizer_cases=sanitizer['cases'],sanitizer_stage_steps=sanitizer['compared_stage_steps'],
            tolerance=release['tolerance'],state_invariant_checks=audit['state_invariants']['checks'],
            rejected_unsupported_requests=len(audit['negative_capabilities']),
            deliberately_wrong_damage_detected_cases=negative['cases']-negative['passed_cases'],
            no_V_runtime_in_stage_library=True,
            original_full_suite_rerun=False,full_same_rule_battle_comparison=False,
            real_PC_game_validation=False,APK_built=False,device_test=False,performance_measured=False),
        inventory=inventory,production_binary=production,
        blockers=['没有TypedWorld接管NativeBattle的唯一权威状态；五个阶段不是完整后端。',
            '原版僵尸/实体/植物维护、bonus_scan、targets.context、gate及PvP覆盖链尚未完整迁移。',
            '英雄、状态交互、秘籍、AI、输入、绘制、联机、观战和回放尚未接入类型化状态。',
            '源逻辑盘点未闭合，mapgen恢复文本语法截断仍保留为问题。',
            '未跑类型化全量旧套件/35场景完整对拍，没有正式性能与成品验收。'],
        next_work=['逐个核对当前有效的PvP伤害/实体构造包装层并迁入显式类型接口。',
            '迁移完整僵尸区域与英雄输入/地图状态，形成方案E1定义的真实逐刻闭环。',
            '提供实际TypedWorld入口、独立双世界对拍与旧测试夹具访问桥，然后继续E2/E3。'],
        modified_preexisting_files=changed,unexpected_source_drift=unrelated,missing_sources=missing,
        source_files={str(p.relative_to(ROOT)):sha(p) for p in source_paths if p.is_file()},
        evidence={str(p.relative_to(ROOT)):sha(p) for p in evidence_paths})
    (RUN/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(checkpoint_verification_passed=valid_checkpoint,status='incomplete',release_ready=False,
                         source_files=len(report['source_files']),unexpected_source_drift=unrelated,missing_sources=missing)))
    return 0 if valid_checkpoint else 1


if __name__=='__main__':sys.exit(main())
