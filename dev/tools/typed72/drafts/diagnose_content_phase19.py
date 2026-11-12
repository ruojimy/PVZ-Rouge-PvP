"""Read-only comparison of retained phase19 evidence after removing probe ledger noise."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
from evidence_archive import open_evidence
from verify_entities import difference
run=ROOT/'test_results/content_zombies_child/phase19_v6_r1'
results=[]
with open_evidence(run/'actual.jsonl') as actual,open_evidence(run/'expected.jsonl') as expected:
    for index,(a,e) in enumerate(zip(actual,expected)):
        got=json.loads(a);want=json.loads(e)
        if 6<=index<=14:
            for step in got:
                step['lifecycle_calls']=[call for call in step['lifecycle_calls'] if call[0] not in ('pea_player','damage')]
        diff=difference(want,got);results.append(dict(case=index,difference=diff));print(index,json.dumps(diff,ensure_ascii=False))
destination=ROOT/'test_results/content_zombies_child/phase19_v6_diagnostic'
destination.mkdir(exist_ok=True)
(destination/'ledger-only.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
