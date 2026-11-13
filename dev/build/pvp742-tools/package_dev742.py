"""Stage the reviewed developer tree, preserving source provenance.

This CLI stages/verifies only. create_utf8_archive() is available for a later,
explicit finalization step; this script never calls it during staging.
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
BASE = ROOT / 'build/github-pvp741-20261113/dev'
STAGE = HERE / 'staging'
MANIFEST = 'MANIFEST-PvP74.2.json'
SUMS = 'SHA256SUMS.txt'
STATUS = 'STAGING_STATUS.json'
EVIDENCE_SUMS = 'test_results/PVP742-EVIDENCE-SHA256SUMS.txt'
RESULT_DOCS = ['docs/PVP742_专项验收与剩余问题.md', 'docs/PVP742_性能与交付.md']
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
               'PvP74.1_进度.md', 'PvP74.2_任务清单.md',
               '更新说明-PvP73.md', '更新说明-PvP73.1.md',
               '更新说明-PvP74.md', '更新说明-PvP74.1.md',
               '更新说明-PvP74.2.md',
               'build/typed72-integrated-v44/integration-manifest.json']
GENERATED_SOURCE_FILES = {
    'README.md': 'build/pvp742-tools/README-PvP74.2-dev.md',
    '开发者包说明-PvP74.2.md': 'build/pvp742-tools/开发者包说明-PvP74.2.md',
    'build/pvp742-tools/package_dev742.py': 'build/pvp742-tools/package_dev742.py',
    'build/pvp742-tools/README-PvP74.2-dev.md': 'build/pvp742-tools/README-PvP74.2-dev.md',
    'build/pvp742-tools/开发者包说明-PvP74.2.md': 'build/pvp742-tools/开发者包说明-PvP74.2.md',
    'build/pvp742-tools/sync_cattail_mark_text742.py': 'build/pvp742-tools/sync_cattail_mark_text742.py',
    'docs/history/README-before-PvP74.2.md': 'build/github-pvp741-20261113/dev/README.md',
    'test_results/pvp742/README-curated-evidence.md': 'build/pvp742-tools/evidence-guide742.md',
    'build/pvp742-tools/evidence-guide742.md': 'build/pvp742-tools/evidence-guide742.md',
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
]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_stage():
    expected = ROOT / 'build/pvp742-tools/staging'
    if STAGE.resolve() != expected.resolve() or STAGE.parent.resolve() != HERE.resolve():
        raise RuntimeError('stage escaped its explicitly named workspace directory')
    if STAGE.is_symlink() or (STAGE.exists() and getattr(STAGE.stat(), 'st_file_attributes', 0) & 0x400):
        raise RuntimeError('stage is a symlink/junction')


def allowed(rel):
    parts = Path(rel).parts
    name = parts[-1]
    low = name.lower()
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


def make_plan():
    plan = {rel: (path, 'reviewed-pvp741-dev', rel) for rel, path in walk(BASE)}
    for prefix in OWNED_DIRS + ['third_party/' + name for name in THIRD_PARTY]:
        # Authoritative overlays also remove stale files deleted from current owners.
        plan = {rel: value for rel, value in plan.items() if rel != prefix and not rel.startswith(prefix + '/')}
        for rel, path in walk(ROOT / prefix, prefix):
            plan[rel] = (path, 'current-workspace', rel)
    for rel in OWNED_FILES:
        source = ROOT / rel
        if source.is_file() and allowed(rel):
            plan[rel] = (source, 'current-workspace', rel)
    plan.pop(SUMS, None)
    for rel, source_rel in GENERATED_SOURCE_FILES.items():
        source = ROOT / source_rel
        if BASE in source.parents:
            plan[rel] = (source, 'reviewed-pvp741-dev', source.relative_to(BASE).as_posix())
        else:
            plan[rel] = (source, 'pvp742-staging-guide', source_rel)
    selected, evidence = select_evidence()
    for rel in selected:
        plan[rel] = (ROOT / rel, 'curated-pvp742-evidence', rel)
    missing = [rel for rel in REQUIRED if rel not in plan]
    if missing:
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
        if not (rel.startswith('test_results/pvp742/') or rel.startswith('test_results/pvp742-terrain-')):
            reason = 'outside curated PvP74.2 evidence scope'
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
    return selected, {'selection': 'document references plus reviewed summaries/assessments and small fixed-input JSON',
                      'selected_paths': selected,
                      'omitted_document_references': omitted,
                      'raw_logs_large_states_and_private_device_samples_included': False}


class Utf8ZipInfo(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):
        return self.filename.encode('utf-8'), self.flag_bits | 0x800


def utf8_policy_test():
    buffer = io.BytesIO()
    names = ['PvZ-PvP-Native-PvP74.2-src/README.md',
             'PvZ-PvP-Native-PvP74.2-src/开发者包说明-PvP74.2.md']
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(Utf8ZipInfo(name), 'UTF-8 名称测试'.encode('utf8'))
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        if archive.namelist() != names or any(not item.flag_bits & 0x800 for item in archive.infolist()):
            raise RuntimeError('ZIP UTF-8 filename policy failed')
    return {'passed': True, 'utf8_flag_on_every_entry': True, 'in_memory_only': True}


def create_utf8_archive(stage, output):
    """For explicit later finalization only; never invoked by this staging CLI."""
    if output.exists():
        raise RuntimeError('archive already exists')
    prefix = 'PvZ-PvP-Native-PvP74.2-src/'
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
    archives = sorted((ROOT / 'dist').glob('*pvp741*Developer-Package.zip'))
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
                'canonical_chinese_guide_name_present': 'PvZ-PvP-Native-PvP74.1-src/开发者包说明-PvP74.1.md' in archive.namelist(),
                'decision': 'Use reviewed Git dev source paths. Old Chinese filenames decode correctly; terminal garbling is not archive corruption. Force UTF-8 flags for all new entries.'}


def stage(refresh=False):
    safe_stage()
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
    evidence_rows = [row for row in rows if row['origin'] == 'curated-pvp742-evidence']
    evidence_raw = ('\n'.join('%s *%s' % (row['sha256'], row['path']) for row in evidence_rows) + '\n').encode('utf8')
    (STAGE / EVIDENCE_SUMS).parent.mkdir(parents=True, exist_ok=True)
    (STAGE / EVIDENCE_SUMS).write_bytes(evidence_raw)
    rows.append({'path': EVIDENCE_SUMS, 'bytes': len(evidence_raw),
                 'sha256': hashlib.sha256(evidence_raw).hexdigest(),
                 'origin': 'staging-metadata', 'source': None, 'source_sha256': None})
    final_summary = json.loads((ROOT / 'test_results/pvp742/full-suite-r4/summary.json').read_text('utf8'))
    comparison = json.loads((ROOT / 'test_results/pvp742/regression-comparison-final.json').read_text('utf8'))
    if not comparison['no_new_outcome_regressions'] or not final_summary['pure_typed_gate']['passed']:
        raise RuntimeError('Final regression equivalence or typed gate has not passed')
    status = {'version': 'PvP74.2', 'status': 'source-ready-PC-validated-Android-device-pending',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'full_regression_counts': final_summary['counts'],
              'new_nonpass': comparison['new_nonpass'],
              'pure_typed_gate_passed': True,
              'pending': ['real Android performance/device acceptance',
                          'reported unreproduced crashes and long-session memory growth'],
              'contains_user_saves_or_raw_device_logs': False,
              'final_zip_created_by_this_run': False}
    raw = (json.dumps(status, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    (STAGE / STATUS).write_bytes(raw)
    rows.append({'path': STATUS, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                 'origin': 'staging-metadata', 'source': None, 'source_sha256': None})
    manifest = {'version': 'PvP74.2', 'status': 'staging',
                'reviewed_base': BASE.relative_to(ROOT).as_posix(),
                'old_archive_reference': old_archive_reference(),
                'utf8_zip_policy_test': utf8_policy_test(),
                'curated_evidence': evidence,
                'third_party_prebuilt_exception': 'SDL lib/{x64,x86} dependencies; project compile outputs excluded',
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
            source_root = BASE if row['origin'] == 'reviewed-pvp741-dev' else ROOT
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    result = verify() if args.verify_only else stage(args.refresh)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
