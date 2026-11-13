"""Compare unchanged native test identities, preserving every raw non-pass.

Counts alone can hide one resolved failure plus a new failure. This report
compares outcomes per identity, lists changed failure details for review, and
never changes the suite, assertions, waiver policy, or reference artifacts.
"""
import argparse
import collections
import json
import re
from pathlib import Path


def read(directory):
    collection = json.loads((directory / 'collection.json').read_text('utf8'))
    rows = {}
    duplicates = []
    completed = []
    for module in collection:
        path = directory / (module + '.json')
        status = directory / (module + '.status.json')
        if not path.exists() or not status.exists():
            continue
        completed.append(module)
        for row in json.loads(path.read_text('utf8')):
            key = '.'.join(row[k] for k in ('module', 'class', 'test'))
            if key in rows:
                duplicates.append(key)
            rows[key] = row
    return collection, completed, rows, duplicates


def normalize(detail):
    # Address-only fixture identity failure and catalog checksums vary by run.
    # All unnormalized raw details remain in the report for review.
    detail = re.sub(r'(?<=AssertionError: )\d{11,}(?= not found in \{\})', '<address>', detail)
    detail = re.sub(r'\b[0-9a-f]{64}\b', '<sha256>', detail)
    return detail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--current', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    old_collection, _, before, old_duplicates = read(args.baseline)
    collection, modules, now, duplicates = read(args.current)
    expected = {identity for ids in collection.values() for identity in ids}
    missing = sorted(expected - now.keys())
    extra = sorted(now.keys() - expected)
    new_nonpass = []
    resolved = []
    outcome_changes = []
    detail_changes = []
    for key, row in sorted(now.items()):
        previous = before.get(key)
        if previous is None or row['outcome'] != previous['outcome']:
            outcome_changes.append(dict(id=key, before=previous, current=row))
        if row['outcome'] != 'PASS' and (previous is None or previous['outcome'] == 'PASS'):
            new_nonpass.append(key)
        if row['outcome'] == 'PASS' and previous and previous['outcome'] != 'PASS':
            resolved.append(key)
        if row['outcome'] != 'PASS' and previous and row['detail'] != previous['detail']:
            detail_changes.append(dict(id=key, normalized_equal=normalize(row['detail']) == normalize(previous['detail']),
                                      before=previous['detail'], current=row['detail']))
    summary_path = args.current / 'summary.json'
    summary = json.loads(summary_path.read_text('utf8')) if summary_path.exists() else None
    complete = not missing and not extra and len(modules) == len(collection) and summary is not None
    source_frozen = summary is not None and not summary['source_changed_during_run'] and not summary['fixture_changed_during_run'] and not summary['exe_changed_during_run']
    result = dict(complete=complete, source_frozen=source_frozen,
                  baseline=str(args.baseline), current=str(args.current),
                  collection_equal=collection == old_collection,
                  expected=len(expected), observed=len(now), modules_completed=len(modules),
                  current_counts=dict(collections.Counter(r['outcome'] for r in now.values())),
                  baseline_counts=dict(collections.Counter(r['outcome'] for r in before.values())),
                  duplicates=duplicates, baseline_duplicates=old_duplicates, missing=missing, extra=extra,
                  new_nonpass=new_nonpass, resolved=resolved, outcome_changes=outcome_changes,
                  nonpass_detail_changes=detail_changes,
                  no_new_outcome_regressions=complete and source_frozen and not new_nonpass and not outcome_changes,
                  pure_typed_gate=summary.get('pure_typed_gate') if summary else None,
                  scope='Outcome equivalence is separate from all-green acceptance. Changed raw failure details require review; address/checksum normalization does not waive a failure.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: result[k] for k in ('complete', 'source_frozen', 'observed', 'current_counts', 'new_nonpass', 'no_new_outcome_regressions')}))
    return 0 if result['no_new_outcome_regressions'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
