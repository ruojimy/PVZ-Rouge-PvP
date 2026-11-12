"""Exact temporary native-test waivers; raw outcomes are never rewritten."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT_POLICY = Path(__file__).resolve().parents[1]/'docs/coverage/temporary-native-waivers.json'


def detail_sha256(detail):
    return hashlib.sha256(detail.encode('utf-8')).hexdigest()


def load_waivers(path=DEFAULT_POLICY):
    policy = json.loads(Path(path).read_text('utf-8'))
    if policy.get('schema_version') != 1 or policy.get('status') != 'temporary':
        raise ValueError('Invalid temporary native waiver policy')
    cases = policy.get('cases')
    if not isinstance(cases, list):
        raise ValueError('Waiver cases must be an explicit list')
    result = {}
    for case in cases:
        if not isinstance(case,dict):
            raise ValueError('Waiver case must be an object')
        case_id = case.get('id', '')
        if not re.fullmatch(r'test_pvp_[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+', case_id):
            raise ValueError('Waiver requires one exact test identity: '+case_id)
        if case_id in result:
            raise ValueError('Duplicate waiver identity: '+case_id)
        if case.get('outcome') not in ('FAIL', 'ERROR'):
            raise ValueError('Only an existing FAIL or ERROR can be waived: '+case_id)
        if not re.fullmatch(r'[0-9a-f]{64}', case.get('detail_sha256', '')) or not case.get('reason'):
            raise ValueError('Waiver requires an exact detail SHA256 and a reason: '+case_id)
        result[case_id] = case
    return result


def evaluate_module(module, expected_ids, results, returncode, hero_violations=0,
                    report_error=None, waivers=None):
    """Accept only complete, structurally valid results and exact known failures.

    Native return code 1 is expected only when the complete report has FAIL/ERROR
    rows. A crash, timeout or inconsistent exit is never a test-case waiver.
    """
    waivers = waivers or {}
    expected = set(expected_ids)
    infrastructure = []
    if not expected:
        infrastructure.append('empty_expected_collection')
    if report_error:
        infrastructure.append('report_error: '+str(report_error))
    if hero_violations:
        infrastructure.append('hero_guard_violations')
    rows = []
    if not isinstance(results, list):
        infrastructure.append('report_is_not_a_list')
    else:
        for row in results:
            if (not isinstance(row, dict) or
                    any(not isinstance(row.get(k), str) for k in ('module', 'class', 'test', 'outcome', 'detail')) or
                    row['outcome'] not in ('PASS', 'FAIL', 'ERROR', 'SKIP')):
                infrastructure.append('malformed_test_row')
                continue
            rows.append(row)
    identity = lambda row: '.'.join(row[k] for k in ('module', 'class', 'test'))
    ids = [identity(row) for row in rows]
    seen = set(ids)
    missing = sorted(expected-seen)
    extra = sorted(seen-expected)
    duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
    if missing: infrastructure.append('missing_results')
    if extra: infrastructure.append('extra_results')
    if duplicates: infrastructure.append('duplicate_results')
    if any(row['module'] != module for row in rows):
        infrastructure.append('wrong_module_results')
    counts = {key: sum(row['outcome'] == key for row in rows) for key in ('PASS', 'FAIL', 'ERROR', 'SKIP')}
    expected_exit = 1 if counts['FAIL'] or counts['ERROR'] else 0
    if type(returncode) is not int or returncode != expected_exit:
        infrastructure.append('unexpected_process_exit')
    applied, unexpected, resolved = [], [], []
    for row in rows:
        case_id = identity(row)
        case = waivers.get(case_id)
        if row['outcome'] == 'PASS':
            if case: resolved.append(case_id)
            continue
        digest = detail_sha256(row['detail'])
        if case and row['outcome'] == case['outcome'] and digest == case['detail_sha256']:
            applied.append(dict(id=case_id, outcome=row['outcome'], detail_sha256=digest, reason=case['reason']))
        else:
            unexpected.append(dict(id=case_id, outcome=row['outcome'], detail_sha256=digest,
                                   reason='waiver_signature_changed' if case else 'not_waived'))
    raw_success = not infrastructure and not any(counts[key] for key in ('FAIL', 'ERROR', 'SKIP'))
    return dict(success=raw_success, accepted=not infrastructure and not unexpected,
                counts=counts, missing=missing, extra=extra, duplicates=duplicates,
                infrastructure_errors=infrastructure, waived=applied,
                unexpected_nonpass=unexpected, resolved_waivers=resolved)
