"""Stage the reviewed developer tree, preserving source provenance.

Only --inheritance-only and --plan-only are used before the release freeze.
Staging/finalization require an explicit freeze record and the exact 74.3 version.
No command in this tool executes game, regression, or device tests.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'build/github-pvp742-20261114/dev'
STAGE = HERE / 'staging'
MANIFEST = 'MANIFEST-PvP74.3.json'
EXPECTED_BUILD = '1.6.0.74.3-typed.20261114'
OUTPUT = ROOT / 'dist/PvZ-PvP-Native-20261114-pvp743-r1-Developer-Package.zip'
FREEZE = HERE / 'release-freeze.json'
INHERITANCE = HERE / 'source-inheritance.json'
SUMS = 'SHA256SUMS.txt'
STATUS = 'STAGING_STATUS.json'
EVIDENCE_SUMS = 'test_results/PVP743-EVIDENCE-SHA256SUMS.txt'
RESULT_DOCS = ['docs/PVP742_专项验收与剩余问题.md', 'docs/PVP742_性能与交付.md',
               'PvP74.3_任务总清单.md', '更新说明-PvP74.3.md',
               'test_results/pvp742/crowd-stack-assessment.md',
               'test_results/pvp742/conveyor-deployment-assessment.md',
               'test_results/pvp742/conveyor-guest-assessment.md',
               'test_results/pvp742/rage-resource-assessment.md']
EVIDENCE_SEEDS = [
    'test_results/pvp742/full-suite-r4/summary.json',
    'test_results/pvp742/full-suite-r4/pure-typed-gate/pure-typed-gate.json',
    'test_results/pvp742/regression-comparison-final.json',
    'test_results/pvp742/test-interpreter-audit.json',
    'test_results/pvp742/targeting-buffer-absolute.json',
    'test_results/pvp742/special-movement-contract-assessment.md',
    'test_results/pvp742/pc-archive-verification-r2.json',
    'test_results/pvp742/pc-package-smoke-r2/result.json',
    'test_results/pvp742/android-r5-verification.json',
    'test_results/pvp742/local-delivery-verification.json',
    'test_results/pvp742/fatal-log-audit-r2/result.json',
    'test_results/pvp742/targeting-full-r1/summary.json',
    'test_results/pvp742/application-performance-r3/summary.json',
    'test_results/pvp742/final-directed-r1/summary.json',
    'test_results/pvp742/final-directed-r1/fire741_production_audit.json',
    'test_results/pvp742/final-directed-r1/pvp741_combat_audit.json',
    'test_results/pvp742/final-directed-r1/pvp742_performance_audit.json',
    'test_results/pvp742/guest-snapshot-memory-r2/summary.json',
    'test_results/pvp742/guest-render-memory-flat-r5/summary.json',
    'test_results/pvp742/guest-render-memory-grabber60-r6/summary.json',
    'test_results/pvp742/guest-render-memory-grabber120-r7/summary.json',
    'test_results/pvp742/guest-render-memory-analysis.json',
    'test_results/pvp742/dense-crash/summary.json',
    'test_results/pvp742/catalog-text-final.json',
    'test_results/pvp742/catalog-text-cattail-final.json',
    'test_results/pvp742/cattail-mark-text-sync.json',
    'test_results/pvp742/cattail-text-regeneration-proof.json',
    'test_results/pvp742/cattail-head-contract-assessment.md',
    'test_results/pvp742/cold-catalog-text-sync.json',
    'test_results/pvp742/ui-regressions/summary.json',
    'test_results/pvp742/texture-full-regression/summary.json',
    'test_results/pvp742/imp-armor-r1.json',
    'test_results/pvp742/secondhand-r2.json',
    'test_results/pvp742/secondhand-assessment.md',
    'test_results/pvp742/self-destruct-assessment.md',
    'test_results/pvp742/network-null-battle-assessment.md',
    'test_results/pvp742/null-battle-suite-r1/summary.json',
    'test_results/pvp742/null-battle-pure-gate-r2/pure-typed-gate.json',
    'test_results/pvp742/null-battle-pure-gate-r2/output-integrity.json',
    'test_results/pvp742/map-key-assessment.md',
    'test_results/pvp742/map-key-r3.json',
    'test_results/pvp742/occupancy-comparison.json',
    'test_results/pvp742/occupancy-new.json',
    'test_results/pvp742/occupancy-old.json',
    'test_results/pvp742/multifire-r2.json',
    'test_results/pvp742/reverse-subscription-assessment.md',
    'test_results/pvp742/reverse-subscription-prototype.json',
    'test_results/pvp742/throw-trace-audit.txt',
    'test_results/pvp742/crowd-stack-assessment.md',
    'test_results/pvp742/crowd-stack-summary.json',
    'test_results/pvp742/crowd-stack-r3-pinned/spatial-equivalence.json',
    'test_results/pvp742/crowd-stack-r5-final/default40-population-equivalence.json',
    'test_results/pvp742/conveyor-deployment-assessment.md',
    'test_results/pvp742/conveyor-deployment-r2.json',
    'test_results/pvp742/conveyor-guest-assessment.md',
    'test_results/pvp742/conveyor-guest-r3.json',
    'test_results/pvp742/rage-resource-assessment.md',
    'test_results/pvp742/three-issues-followup/population-assessment.md',
    'test_results/pvp742/three-issues-followup/population-after.json',
    'test_results/pvp743/local-delivery-verification.json',
]

OWNED_DIRS = [
    'src', 'android', 'tools', 'docs', 'developer-tools', 'fonts',
    'extract/data', 'extract/schema', 'extract/assets', 'extract/original',
    'extract/live', 'extract/golden',
    'build/typed72-integrated-v44/source', 'build/typed72-match-v1',
    'build/ai-nn',
]
THIRD_PARTY = ['SDL2-2.30.9', 'SDL2_image-2.8.2', 'SDL2_mixer-2.8.0',
               'SDL2_ttf-2.22.0', 'nlohmann', 'zlib-1.3.2-compress']
OWNED_FILES = ['CMakeLists.txt', 'AGENTS.md', '启动PvP.cmd', '待办.md',
               '工作汇总.md', 'PvP73_进度.md', 'PvP74_进度.md',
               'PvP74.1_进度.md', 'PvP74.2_任务清单.md', 'PvP74.3_任务总清单.md',
               '更新说明-PvP73.md', '更新说明-PvP73.1.md',
               '更新说明-PvP74.md', '更新说明-PvP74.1.md',
               '更新说明-PvP74.2.md', '更新说明-PvP74.3.md', '更新公告-PvP74.3.txt',
               'build/typed72-integrated-v44/integration-manifest.json']
GENERATED_SOURCE_FILES = {
    'README.md': 'build/pvp743-tools/README-PvP74.3-dev.md',
    '开发者包说明-PvP74.3.md': 'build/pvp743-tools/开发者包说明-PvP74.3.md',
    'build/pvp743-tools/package_dev743.py': 'build/pvp743-tools/package_dev743.py',
    'build/pvp743-tools/package_pc743.py': 'build/pvp743-tools/package_pc743.py',
    'build/pvp743-tools/README-PvP74.3-dev.md': 'build/pvp743-tools/README-PvP74.3-dev.md',
    'build/pvp743-tools/开发者包说明-PvP74.3.md': 'build/pvp743-tools/开发者包说明-PvP74.3.md',
    'build/pvp743-tools/evidence-guide743.md': 'build/pvp743-tools/evidence-guide743.md',
    'build/pvp743-tools/source-inheritance.json': 'build/pvp743-tools/source-inheritance.json',
    'build/pvp743-tools/source-inheritance.md': 'build/pvp743-tools/source-inheritance.md',
    'build/pvp743-tools/release-freeze.json': 'build/pvp743-tools/release-freeze.json',
    'docs/history/README-before-PvP74.3.md': 'build/github-pvp742-20261114/dev/README.md',
    'docs/history/README-before-PvP74.2.md': 'build/github-pvp742-20261114/dev/docs/history/README-before-PvP74.2.md',
    'docs/history/MANIFEST-PvP74.2.json': 'build/github-pvp742-20261114/dev/MANIFEST-PvP74.2.json',
    'docs/history/STAGING_STATUS-PvP74.2.json': 'build/github-pvp742-20261114/dev/STAGING_STATUS.json',
    'test_results/pvp743/README-curated-evidence.md': 'build/pvp743-tools/evidence-guide743.md',
}
SKIP_DIRS = {'__pycache__', '.git', '.gradle', '.cxx', '.idea', '.vscode',
             'CMakeFiles', 'Debug', 'Release', 'RelWithDebInfo', 'MinSizeRel',
             'pvp_userdata', 'userdata', 'user_data', 'saves', 'replays',
             'backup-latest', 'node_modules'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.obj', '.o', '.pdb', '.ilk', '.exp', '.exe',
                 '.dll', '.lib', '.so', '.a', '.apk', '.dex', '.class', '.jar',
                 '.aar', '.log', '.tlog', '.lastbuildstate', '.sln', '.vcxproj',
                 '.filters', '.user', '.keystore', '.jks', '.pem', '.key',
                 '.p12', '.pfx', '.zip', '.7z', '.orig', '.tmp'}
TEXT_SUFFIXES = {'.py', '.cpp', '.h', '.hpp', '.inc', '.md', '.txt', '.json',
                 '.sh', '.ps1', '.cmd', '.bat', '.cmake', '.xml', '.gradle'}
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|'
                    rb'gh[pousr]_[A-Za-z0-9]{30,}|'
                    rb'(?:sk-proj-|sk-ant-)[A-Za-z0-9_-]{24,}')
REQUIRED = [
    'CMakeLists.txt', 'android/CMakeLists.txt', 'android/build_native.sh',
    'android/build_apk.sh', 'tools/typed72/make_app_composition.py',
    'tools/typed72/production_observers.py',
    'tools/pvp74_apply_hooks.py', 'tools/pvp741_apply_hooks.py',
    'tools/pvp741_hooks.json', 'tools/pvp74_resource_catalog.py',
    'build/typed72-match-v1/match_probe.cpp',
    'build/typed72-match-v1/frame_layer.inc',
    'build/typed72-match-v1/snapshot_layer.inc',
    'build/typed72-match-v1/make_stripped.py',
    'src/sim/typed72_app/composition/MANIFEST.json',
    'build/typed72-integrated-v44/source/src/sim/typed/cold_catalog_data.cpp',
    'build/typed72-integrated-v44/source/src/sim/typed/cold_card_fields.h',
    'build/typed72-integrated-v44/source/src/sim/typed/native_canvas.h',
    'src/uitools/pvp742_guest_render_memory_audit.cpp',
    'tools/test/pvp742_guest_render_memory_audit.py',
    'build/ai-nn/README.md', 'build/ai-nn/cold-corpus/index.json',
    'build/ai-nn/cold-corpus/atlas.bin.gz',
    'third_party/SDL2-2.30.9/lib/x64/SDL2.lib',
    'third_party/SDL2_image-2.8.2/lib/x64/SDL2_image.lib',
    'third_party/SDL2_mixer-2.8.0/lib/x64/SDL2_mixer.lib',
    'third_party/SDL2_ttf-2.22.0/lib/x64/SDL2_ttf.lib',
    'PvP74.3_任务总清单.md', '更新说明-PvP74.3.md', '更新公告-PvP74.3.txt',
    'src/uitools/pvp742_crowd_stack_audit.cpp',
    'src/uitools/pvp742_population_entry_audit.cpp',
    'src/uitools/pvp742_conveyor_deployment_audit.cpp',
    'src/uitools/pvp742_conveyor_guest_display_audit.cpp',
]

INHERITANCE_SCOPES = ['src', 'build/typed72-integrated-v44/source/src/sim/typed',
                      'build/typed72-match-v1']
CRITICAL_GROUPS = {
    'giant_imp_secondhand': [
        'build/typed72-integrated-v44/source/src/sim/typed/cold_admission.cpp',
        'build/typed72-integrated-v44/source/src/sim/typed/service_plants.cpp',
        'build/typed72-integrated-v44/source/src/sim/typed/zombie_secret_runtime.cpp',
        'build/typed72-integrated-v44/source/src/sim/typed/zombie_secret_runtime.h',
        'src/uitools/pvp742_secondhand_audit.cpp'],
    'plant_targeting_spatial': [
        'build/typed72-integrated-v44/source/src/sim/typed/moving_coverage_grid.h',
        'build/typed72-integrated-v44/source/src/sim/typed/content_queries.cpp',
        'build/typed72-integrated-v44/source/src/sim/typed/content_target.cpp',
        'build/typed72-integrated-v44/source/src/sim/typed/targets.cpp',
        'src/uitools/pvp742_targeting_bench.cpp'],
    'network_refresh_and_plant2_sequence': [
        'src/ui/gen/pm_app.cpp', 'src/ui/hand/pressure_pacing.cpp',
        'src/ui/hand/pressure_pacing.h', 'tools/pvp741_hooks.json',
        'src/uitools/pvp742_network_refresh_audit.cpp',
        'tools/test/pvp742_network_refresh_audit.py'],
    'allocator': ['src/core/alloc.cpp', 'src/core/alloc.h',
                  'src/tools/pvp742_allocator_audit.cpp'],
    'match_owner': ['build/typed72-match-v1/match_probe.cpp',
                    'build/typed72-match-v1/frame_layer.inc',
                    'build/typed72-match-v1/snapshot_layer.inc',
                    'tools/typed72/make_app_composition.py'],
}


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_stage():
    expected = ROOT / 'build/pvp743-tools/staging'
    if STAGE.resolve() != expected.resolve() or STAGE.parent.resolve() != HERE.resolve():
        raise RuntimeError('stage escaped its explicitly named workspace directory')
    if STAGE.is_symlink() or (STAGE.exists() and getattr(STAGE.stat(), 'st_file_attributes', 0) & 0x400):
        raise RuntimeError('stage is a symlink/junction')


def allowed(rel):
    parts = Path(rel).parts
    name = parts[-1]
    low = name.lower()
    if low in {'userdata-before.json', 'userdata-after.json'}:
        return False  # Local user-file paths/hashes are never distributable evidence.
    if any(p in SKIP_DIRS or p.startswith('cmake-build-') for p in parts[:-1]):
        return False
    if rel.startswith('build/typed72-match-v1/build/'):
        return False
    if low.startswith('.env') or low in {'local.properties', 'keystore.env'}:
        return False
    if fnmatch.fnmatch(low, '*.bak*') or low.startswith('提示词_'):
        return False
    if low.endswith('.pvp-replay.json'):
        return False
    if any(marker in low for marker in ('logcat', 'getprop', '直播快照', 'live-snapshot')) and Path(low).suffix not in {'.py', '.ps1', '.sh', '.cpp', '.h'}:
        return False
    suffix = Path(low).suffix
    # These are reviewed build dependencies, not products of this project.
    third_party_binary = rel.startswith('third_party/') and '/lib/' in rel and suffix in {'.dll', '.lib', '.a', '.so'}
    return suffix not in SKIP_SUFFIXES or third_party_binary


def walk(folder, relative_prefix=''):
    if not folder.is_dir():
        raise RuntimeError('required input directory missing: ' + str(folder))
    for current, dirs, files in os.walk(folder, followlinks=False):
        directory = Path(current)
        kept = []
        for name in sorted(dirs):
            candidate = directory / name
            relative = candidate.relative_to(folder).as_posix()
            rel = relative_prefix + '/' + relative if relative_prefix else relative
            if candidate.is_symlink() or getattr(candidate.stat(), 'st_file_attributes', 0) & 0x400:
                raise RuntimeError('input link/junction rejected: ' + rel)
            if name not in SKIP_DIRS and not name.startswith('cmake-build-') and not rel.startswith('build/typed72-match-v1/build'):
                kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            candidate = directory / name
            relative = candidate.relative_to(folder).as_posix()
            rel = relative_prefix + '/' + relative if relative_prefix else relative
            if candidate.is_symlink() or getattr(candidate.stat(), 'st_file_attributes', 0) & 0x400:
                raise RuntimeError('input link rejected: ' + rel)
            if allowed(rel):
                yield rel, candidate


def make_plan(allow_pending=False, skip_freeze=False):
    plan = {rel: (path, 'reviewed-pvp742-dev', rel) for rel, path in walk(BASE)}
    for prefix in OWNED_DIRS + ['third_party/' + name for name in THIRD_PARTY]:
        # Authoritative overlays also remove stale files deleted from current owners.
        plan = {rel: value for rel, value in plan.items() if rel != prefix and not rel.startswith(prefix + '/')}
        for rel, path in walk(ROOT / prefix, prefix):
            plan[rel] = (path, 'current-workspace', rel)
    for rel in OWNED_FILES:
        source = ROOT / rel
        if source.is_file() and allowed(rel):
            plan[rel] = (source, 'current-workspace', rel)
    # The old manifest remains evidence in docs/history, not active release metadata.
    for name in (SUMS, STATUS, 'MANIFEST-PvP74.2.json'):
        plan.pop(name, None)
    for rel, source_rel in GENERATED_SOURCE_FILES.items():
        if skip_freeze and source_rel == 'build/pvp743-tools/release-freeze.json':
            continue
        source = ROOT / source_rel
        if not source.is_file():
            if allow_pending:
                continue
            raise RuntimeError('release input missing: ' + source_rel)
        if BASE in source.parents:
            plan[rel] = (source, 'reviewed-pvp742-dev', source.relative_to(BASE).as_posix())
        else:
            plan[rel] = (source, 'pvp743-staging-guide', source_rel)
    selected, evidence = select_evidence()
    for rel in selected:
        plan[rel] = (ROOT / rel, 'curated-history-and-pvp743-evidence', rel)
    missing = [rel for rel in REQUIRED if rel not in plan]
    if missing and not allow_pending:
        raise RuntimeError('missing mandatory source/data/dependency: ' + ', '.join(missing))
    # Every current source/test is included, not just a hand-maintained new-file list.
    for rel, source in walk(ROOT / 'src', 'src'):
        if rel not in plan or plan[rel][0] != source:
            raise RuntimeError('current source omitted or stale: ' + rel)
    return plan, evidence


def select_evidence():
    references = set()
    for rel in RESULT_DOCS:
        path = ROOT / rel
        if path.is_file():
            references.update(re.findall(r'(?:\.\./)?(test_results/[^\s`\)\]<>]+)', path.read_text('utf8')))
    candidates = references | set(EVIDENCE_SEEDS)
    candidates.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'test_results').glob('pvp742-terrain-*.json'))
    candidates.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'test_results/pvp742').glob('allocator*.json'))
    selected, omitted = [], []
    for rel in sorted(candidates):
        path = ROOT / rel
        reason = None
        if path.name.lower() in {'userdata-before.json', 'userdata-after.json'}:
            reason = 'private local user-file paths/hashes; only aggregate delivery verification is distributable'
        elif not (rel.startswith(('test_results/pvp742/', 'test_results/pvp743/', 'test_results/pvp742-terrain-'))):
            reason = 'outside reviewed historical / current evidence scope'
        elif not path.is_file():
            reason = 'not available at this staging pass; final refresh pending'
        elif path.suffix.lower() not in {'.json', '.md', '.txt'}:
            reason = 'raw logs / JSONL / binary evidence intentionally omitted'
        elif any(mark in path.name.lower() for mark in ('live-', 'phoneinfo', 'getprop', 'logcat', 'snapshot-27860')):
            reason = 'private live/device sample intentionally omitted'
        elif path.stat().st_size > 1024 * 1024:
            reason = 'large raw state intentionally omitted; summary and source retained'
        elif not allowed(rel):
            reason = 'excluded payload type'
        if reason:
            if rel in references:
                omitted.append({'path': rel, 'reason': reason})
        else:
            selected.append(rel)
    return selected, {'selection': 'historical 74.2 evidence plus already completed follow-up summaries; no new tests run by packaging',
                      'historical_full_suite_is_not_a_743_full_run': True,
                      'new_game_and_device_validation_skipped_at_user_request': True,
                      'selected_paths': selected,
                      'omitted_document_references': omitted,
                      'raw_logs_large_states_and_private_device_samples_included': False}


def digest_rows(rows):
    value = hashlib.sha256()
    for row in sorted(rows, key=lambda x: x['path']):
        value.update((row['sha256'] + ' *' + row['path'] + '\n').encode('utf8'))
    return value.hexdigest()


def inheritance_audit():
    """Read-only source comparison; writes only the two new packaging reports."""
    plan, _ = make_plan(allow_pending=True, skip_freeze=True)
    base_manifest = json.loads((BASE / 'MANIFEST-PvP74.2.json').read_text('utf8'))
    recorded = {r['path']: r['sha256'] for r in base_manifest['files']}
    scopes, baseline_errors = [], []
    for prefix in INHERITANCE_SCOPES:
        old = {r: p for r, p in walk(BASE / prefix, prefix)}
        current = {r: p for r, p in walk(ROOT / prefix, prefix)}
        changes, unchanged_rows, current_rows = [], [], []
        for rel in sorted(set(old) | set(current)):
            old_sha = sha(old[rel]) if rel in old else None
            new_sha = sha(current[rel]) if rel in current else None
            if old_sha and recorded.get(rel) != old_sha:
                baseline_errors.append(rel)
            if new_sha:
                current_rows.append({'path': rel, 'sha256': new_sha})
                if rel not in plan or plan[rel][0] != current[rel]:
                    raise RuntimeError('current source omitted from package plan: ' + rel)
            if old_sha == new_sha:
                unchanged_rows.append({'path': rel, 'sha256': new_sha})
            else:
                changes.append({'path': rel,
                                'change': 'added' if old_sha is None else 'removed' if new_sha is None else 'modified',
                                'reviewed_742_sha256': old_sha, 'current_sha256': new_sha})
        scopes.append({'scope': prefix, 'reviewed_files': len(old), 'current_files': len(current),
                       'unchanged_files': len(unchanged_rows),
                       'unchanged_set_sha256': digest_rows(unchanged_rows),
                       'current_set_sha256': digest_rows(current_rows),
                       'changes': changes})
    critical = {}
    for group, paths in CRITICAL_GROUPS.items():
        entries = []
        for rel in paths:
            source = ROOT / rel
            if not source.is_file() or rel not in plan or plan[rel][0] != source:
                raise RuntimeError('required inherited contract source absent/stale: ' + rel)
            old = BASE / rel
            current_sha = sha(source)
            entries.append({'path': rel, 'current_sha256': current_sha,
                            'reviewed_742_sha256': sha(old) if old.is_file() else None,
                            'same_as_reviewed_742': old.is_file() and sha(old) == current_sha,
                            'package_source': 'current-workspace'})
        critical[group] = entries
    report = {'kind': 'static-source-inheritance-only',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'reviewed_base': BASE.relative_to(ROOT).as_posix(),
              'reviewed_manifest_sha256': sha(BASE / 'MANIFEST-PvP74.2.json'),
              'baseline_hash_errors': baseline_errors,
              'passed': not baseline_errors, 'scopes': scopes, 'critical_groups': critical,
              'game_or_device_tests_run': False,
              'limitations': 'Byte identity/provenance is not a new behavioral regression result.'}
    INHERITANCE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
    lines = ['# PvP74.3 源码继承静态核对', '',
             '与已审核 PvP74.2 dev 实际文件逐一核对 SHA-256；先核对该基底与其原 manifest 一致。此核对不运行游戏，也不把字节一致当作本轮行为回归。', '',
             '| 范围 | 上版文件 | 当前文件 | 未变化 | 改动 |',
             '| --- | ---: | ---: | ---: | ---: |']
    for item in scopes:
        lines.append('| %s | %d | %d | %d | %d |' % (item['scope'], item['reviewed_files'],
                     item['current_files'], item['unchanged_files'], len(item['changes'])))
    lines.extend(['', '基底摘要不符：%d。完整新旧摘要、未变集合摘要与专项保留文件见 `source-inheritance.json`。' % len(baseline_errors),
                  '', '## 本轮改变的文件', ''])
    for item in scopes:
        for row in item['changes']:
            lines.append('- `%s`：%s。' % (row['path'], row['change']))
    lines.extend(['', '## 重点继承', '',
                  '角斗士巨人/携带小鬼/二手防具、植物空间索敌、客机 move 刷新与 plant2 序号恢复、allocator，以及组合层拥有源均按当前工作区文件进入计划。各文件与上版是否相同及其 SHA-256 在 JSON 的 `critical_groups` 中逐项列出。', '',
                  '本轮按用户最新要求跳过新增对局与实机验证。74.2 全量和旧专项只证明各自记录的构建；本核对不声称 74.3 新全量通过。'])
    (HERE / 'source-inheritance.md').write_text('\n'.join(lines) + '\n', 'utf8')
    if baseline_errors:
        raise RuntimeError('reviewed baseline source differs from its manifest')
    return report


def plan_digest(plan):
    return digest_rows([{'path': rel, 'sha256': sha(item[0])} for rel, item in plan.items()])


def assert_build():
    build = json.loads((ROOT / 'extract/data/__init__.json').read_text('utf8'))['BUILD']
    if build != EXPECTED_BUILD:
        raise RuntimeError('release version not frozen at ' + EXPECTED_BUILD)


def record_freeze():
    assert_build()
    inheritance_audit()
    plan, _ = make_plan(skip_freeze=True)
    report = {'build': EXPECTED_BUILD, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'payload_plan_files_excluding_this_record': len(plan),
              'payload_plan_sha256_excluding_this_record': plan_digest(plan),
              'user_requested_no_new_game_or_device_tests': True,
              'purpose': 'Explicit packaging freeze after parent release coordinator confirmation.'}
    FREEZE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
    return report


def check_freeze():
    assert_build()
    freeze = json.loads(FREEZE.read_text('utf8'))
    plan, _ = make_plan(skip_freeze=True)
    if freeze['build'] != EXPECTED_BUILD or freeze['payload_plan_sha256_excluding_this_record'] != plan_digest(plan):
        raise RuntimeError('release sources/docs changed after explicit freeze; refresh freeze only after coordinator approval')
    return freeze


class Utf8ZipInfo(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):
        return self.filename.encode('utf-8'), self.flag_bits | 0x800


def utf8_policy_test():
    buffer = io.BytesIO()
    names = ['PvZ-PvP-Native-PvP74.3-src/README.md',
             'PvZ-PvP-Native-PvP74.3-src/开发者包说明-PvP74.3.md']
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(Utf8ZipInfo(name), 'UTF-8 名称测试'.encode('utf8'))
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        if archive.namelist() != names or any(not item.flag_bits & 0x800 for item in archive.infolist()):
            raise RuntimeError('ZIP UTF-8 filename policy failed')
    return {'passed': True, 'utf8_flag_on_every_entry': True, 'in_memory_only': True}


def create_utf8_archive(stage, output):
    """For explicit finalization after the release coordinator freezes inputs."""
    if output.exists():
        raise RuntimeError('archive already exists')
    prefix = 'PvZ-PvP-Native-PvP74.3-src/'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                info = Utf8ZipInfo(prefix + path.relative_to(stage).as_posix())
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | (0o755 if path.suffix == '.sh' else 0o644)) << 16
                with path.open('rb') as source, archive.open(info, 'w') as target:
                    shutil.copyfileobj(source, target, 1 << 20)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or any(not info.flag_bits & 0x800 for info in archive.infolist()):
            raise RuntimeError('archive integrity or UTF-8 flags failed')


def old_archive_reference():
    archives = sorted((ROOT / 'dist').glob('*pvp742*Developer-Package.zip'))
    if not archives:
        return {'available': False}
    path = archives[-1]
    with zipfile.ZipFile(path) as archive:
        items = archive.infolist()
        non_ascii = [item for item in items if any(ord(c) > 127 for c in item.filename)]
        return {'available': True, 'path': path.relative_to(ROOT).as_posix(),
                'sha256': sha(path), 'entries': len(items),
                'uncompressed_bytes': sum(i.file_size for i in items),
                'replacement_character_paths': sum('\ufffd' in i.filename for i in items),
                'non_ascii_paths': len(non_ascii),
                'non_ascii_without_utf8_flag': sum(not item.flag_bits & 0x800 for item in non_ascii),
                'canonical_chinese_guide_name_present': 'PvZ-PvP-Native-PvP74.2-src/开发者包说明-PvP74.2.md' in archive.namelist(),
                'decision': 'Use reviewed Git dev source paths. Old Chinese filenames decode correctly; terminal garbling is not archive corruption. Force UTF-8 flags for all new entries.'}


def stage(refresh=False):
    safe_stage()
    freeze = check_freeze()
    plan, evidence = make_plan()
    known = {MANIFEST, SUMS, STATUS, EVIDENCE_SUMS}
    old_manifest = STAGE / MANIFEST
    if STAGE.exists() and any(STAGE.iterdir()):
        if not refresh or not old_manifest.is_file():
            raise RuntimeError('stage exists; use --refresh only for an already manifested stage')
        previous = json.loads(old_manifest.read_text('utf8'))
        old_files = {row['path'] for row in previous['files']}
        present = {p.relative_to(STAGE).as_posix() for p in STAGE.rglob('*') if p.is_file()}
        unexpected = present - old_files - known
        if unexpected:
            raise RuntimeError('unknown files in existing stage: ' + repr(sorted(unexpected)))
        for rel in sorted(old_files - set(plan)):
            target = STAGE / rel
            if target.resolve().parent != STAGE.resolve() and STAGE.resolve() not in target.resolve().parents:
                raise RuntimeError('refuse to remove path outside stage')
            if target.is_file():
                target.unlink()
    STAGE.mkdir(parents=True, exist_ok=True)
    rows = []
    for rel in sorted(plan):
        source, origin, source_rel = plan[rel]
        if source.suffix.lower() in TEXT_SUFFIXES and SECRET.search(source.read_bytes()):
            raise RuntimeError('potential secret material rejected; inspect locally: ' + source_rel)
        before = sha(source)
        target = STAGE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or sha(target) != before:
            shutil.copy2(source, target)
        after, copied = sha(source), sha(target)
        if before != after or before != copied:
            raise RuntimeError('source changed during copy or copied bytes differ: ' + rel)
        rows.append({'path': rel, 'bytes': target.stat().st_size, 'sha256': copied,
                     'origin': origin, 'source': source_rel,
                     'source_sha256': before})
    evidence_rows = [row for row in rows if row['origin'] == 'curated-history-and-pvp743-evidence']
    evidence_raw = ('\n'.join('%s *%s' % (row['sha256'], row['path']) for row in evidence_rows) + '\n').encode('utf8')
    (STAGE / EVIDENCE_SUMS).parent.mkdir(parents=True, exist_ok=True)
    (STAGE / EVIDENCE_SUMS).write_bytes(evidence_raw)
    rows.append({'path': EVIDENCE_SUMS, 'bytes': len(evidence_raw),
                 'sha256': hashlib.sha256(evidence_raw).hexdigest(),
                 'origin': 'staging-metadata', 'source': None, 'source_sha256': None})
    final_summary = json.loads((BASE / 'test_results/pvp742/full-suite-r4/summary.json').read_text('utf8'))
    comparison = json.loads((BASE / 'test_results/pvp742/regression-comparison-final.json').read_text('utf8'))
    status = {'version': 'PvP74.3', 'build': EXPECTED_BUILD,
              'status': 'source-packaged-new-game-and-device-tests-skipped-at-user-request',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'packaging_freeze': freeze,
              'new_full_regression_run': False,
              'new_game_and_device_tests_run_by_packaging': False,
              'latest_user_instruction': 'Continue to package; skip actual testing for now.',
              'historical_742_only': {'full_regression_counts': final_summary['counts'],
                                      'new_nonpass': comparison['new_nonpass'],
                                      'pure_typed_gate_passed': final_summary['pure_typed_gate']['passed'],
                                      'applies_to_743': False},
              'pending': ['new 74.3 full gameplay regression and user/device acceptance',
                          'real Android performance/device acceptance',
                          'reported unreproduced crashes and long-session memory growth'],
              'contains_user_saves_or_raw_device_logs': False,
              'final_zip_created_by_this_run': False}
    raw = (json.dumps(status, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    (STAGE / STATUS).write_bytes(raw)
    rows.append({'path': STATUS, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                 'origin': 'staging-metadata', 'source': None, 'source_sha256': None})
    manifest = {'version': 'PvP74.3', 'build': EXPECTED_BUILD, 'status': 'source-packaged',
                'validation_boundary': status,
                'reviewed_base': BASE.relative_to(ROOT).as_posix(),
                'old_archive_reference': old_archive_reference(),
                'utf8_zip_policy_test': utf8_policy_test(),
                'curated_evidence': evidence,
                'third_party_prebuilt_exception': 'Reviewed SDL lib/{x64,x86} dependencies, including required x64; project compile outputs excluded',
                'historic_frozen_input_exception': 'extract/live/*.marshal and build/ai-nn compressed corpus retained',
                'files': rows}
    (STAGE / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', 'utf8')
    sums = ['%s *%s' % (row['sha256'], row['path']) for row in rows]
    sums.append('%s *%s' % (sha(STAGE / MANIFEST), MANIFEST))
    (STAGE / SUMS).write_text('\n'.join(sums) + '\n', 'utf8')
    return verify()


def verify():
    safe_stage()
    manifest = json.loads((STAGE / MANIFEST).read_text('utf8'))
    rows = manifest['files']
    mismatches = []
    for row in rows:
        target = STAGE / row['path']
        if not target.is_file() or target.stat().st_size != row['bytes'] or sha(target) != row['sha256']:
            mismatches.append({'path': row['path'], 'reason': 'staged payload differs'})
        if row['source']:
            source_root = BASE if row['origin'] == 'reviewed-pvp742-dev' else ROOT
            source = source_root / row['source']
            if not source.is_file() or sha(source) != row['source_sha256']:
                mismatches.append({'path': row['path'], 'reason': 'source hash changed since staging'})
        if not allowed(row['path']):
            mismatches.append({'path': row['path'], 'reason': 'excluded file entered stage'})
    named = {row['path'] for row in rows}
    actual = {path.relative_to(STAGE).as_posix() for path in STAGE.rglob('*') if path.is_file()}
    if actual != named | {MANIFEST, SUMS}:
        mismatches.append({'reason': 'unmanifested or missing paths',
                           'extra': sorted(actual - named - {MANIFEST, SUMS}),
                           'missing': sorted(named - actual)})
    for line in (STAGE / SUMS).read_text('utf8').splitlines():
        value, rel = line.split(' *', 1)
        if sha(STAGE / rel) != value:
            mismatches.append({'path': rel, 'reason': 'SHA256SUMS differs'})
    required_missing = sorted(set(REQUIRED) - actual)
    counts = Counter(row['origin'] for row in rows)
    report = {'passed': not mismatches and not required_missing,
              'stage': STAGE.relative_to(ROOT).as_posix(),
              'payload_files': len(rows), 'all_files': len(actual),
              'payload_bytes': sum(row['bytes'] for row in rows),
              'origins': dict(counts), 'required_missing': required_missing,
              'mismatches': mismatches,
              'manifest_sha256': sha(STAGE / MANIFEST),
              'sha256sums_sha256': sha(STAGE / SUMS),
              'utf8_policy_test': utf8_policy_test(),
              'final_zip_created': False}
    (HERE / 'staging-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
    if not report['passed']:
        raise RuntimeError('staging/source verification failed; see staging-verification.json')
    return report


def finalize():
    check_freeze()
    verification = verify()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    create_utf8_archive(STAGE, OUTPUT)
    expected = {p.relative_to(STAGE).as_posix(): sha(p) for p in STAGE.rglob('*') if p.is_file()}
    prefix = 'PvZ-PvP-Native-PvP74.3-src/'
    mismatches, non_utf8_text, checked = [], [], 0
    with zipfile.ZipFile(OUTPUT) as archive:
        actual = {i.filename[len(prefix):] for i in archive.infolist() if i.filename.startswith(prefix)}
        if actual != set(expected) or len(archive.infolist()) != len(expected):
            raise RuntimeError('ZIP payload file set differs from verified stage')
        for info in archive.infolist():
            rel = info.filename[len(prefix):]
            data = archive.read(info)
            if hashlib.sha256(data).hexdigest() != expected[rel]:
                mismatches.append(rel)
            if Path(rel).suffix.lower() in TEXT_SUFFIXES:
                try:
                    data.decode('utf-8-sig')
                except UnicodeDecodeError:
                    non_utf8_text.append(rel)
            checked += 1
        report = {'passed': not mismatches,
                  'archive': OUTPUT.relative_to(ROOT).as_posix(),
                  'bytes': OUTPUT.stat().st_size, 'sha256': sha(OUTPUT),
                  'entries': len(archive.infolist()), 'per_file_sha256_verified': checked,
                  'crc_all_entries_verified': True,
                  'utf8_flag_on_every_entry': all(i.flag_bits & 0x800 for i in archive.infolist()),
                  'replacement_character_paths': [i.filename for i in archive.infolist() if '\ufffd' in i.filename],
                  'canonical_chinese_guide_present': prefix + '开发者包说明-PvP74.3.md' in archive.namelist(),
                  'sha256_mismatches': mismatches,
                  'historical_text_not_utf8_preserved_verbatim': non_utf8_text,
                  'stage_verification': verification,
                  'new_game_or_device_tests_run': False}
    report['passed'] = bool(report['passed'] and report['utf8_flag_on_every_entry'] and
                            not report['replacement_character_paths'] and report['canonical_chinese_guide_present'])
    (HERE / 'archive-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf8')
    if not report['passed']:
        raise RuntimeError('archive verification failed; preserve archive and inspect report')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--inheritance-only', action='store_true')
    action.add_argument('--plan-only', action='store_true')
    action.add_argument('--record-freeze', action='store_true')
    action.add_argument('--stage', action='store_true')
    action.add_argument('--verify-only', action='store_true')
    action.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    if args.inheritance_only:
        report = inheritance_audit()
        result = {'passed': report['passed'], 'report': INHERITANCE.relative_to(ROOT).as_posix(),
                  'scopes': [{k: v for k, v in item.items() if k != 'changes'} for item in report['scopes']]}
    elif args.record_freeze:
        result = record_freeze()
    elif args.verify_only:
        result = verify()
    elif args.finalize:
        result = finalize()
    elif args.stage:
        result = stage(args.refresh)
    else:
        plan, evidence = make_plan(allow_pending=True, skip_freeze=True)
        result = {'stage_created': False, 'planned_files': len(plan),
                  'origins': dict(Counter(item[1] for item in plan.values())),
                  'pending_required': [rel for rel in REQUIRED if rel not in plan],
                  'curated_evidence_files': len(evidence['selected_paths']),
                  'validation': 'Plan/source inspection only; no game or device tests.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
