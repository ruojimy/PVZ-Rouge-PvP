"""Account for the full legacy inventory, including missing and unexecuted coverage."""
import argparse,collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("run",type=Path);a=ap.parse_args();run=a.run.resolve()
    inventory=json.loads((run/"coverage_map.json").read_text(encoding="utf-8"))
    blocked=json.loads((run/"collection-blocked.json").read_text(encoding="utf-8"))
    identities=json.loads((run/"test-identities.json").read_text(encoding="utf-8"))
    summary=json.loads((run/"summary.json").read_text(encoding="utf-8"));status={s["module"]:s for s in summary["modules"]}
    rows=[];canonical={};executions=collections.Counter();errors=collections.Counter()
    for source in inventory:
        mod=source["module"];s=status.get(mod);row={"module":mod,"legacy_inventory_cases":source["tests"],"theme":source["theme"]}
        if mod in blocked:row.update(status="BLOCKED",reason=blocked[mod])
        elif s:
            row.update(status="EXECUTED",execution=s)
            report=run/(mod+".json")
            results=json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
            idmap={(x["binding"],x["test"]):x["canonical_id"] for x in identities.get(mod,[])}
            for result in results:
                outcome=result["outcome"];executions[outcome]+=1
                identity=idmap.get((result["class"],result["test"]),mod+"."+result["class"]+"."+result["test"])
                canonical.setdefault(identity,[]).append(outcome)
                if outcome!="PASS":errors[result["detail"]]+=1
        elif source["theme"]=="安卓平台" and source["status"]=="待迁移":row.update(status="DEVICE_PENDING",reason="Android functionality and device test migration still required")
        elif source["status"]=="不适用":row.update(status="LEGACY_NA_REVIEW",reason=source["reason"])
        else:row.update(status="UNEXECUTED",reason="Not present in this native run; not covered")
        rows.append(row)
    ranking={"PASS":0,"SKIP":1,"FAIL":2,"ERROR":3}
    unique=collections.Counter(max(outcomes,key=lambda o:ranking.get(o,4)) for outcomes in canonical.values())
    result={"acceptance_passed":False,"legacy_inventory_total":sum(r["tests"] for r in inventory),"inventory_modules":len(rows),"module_states":dict(collections.Counter(r["status"] for r in rows)),"test_execution_counts":dict(executions),"distinct_source_test_outcomes_worst_of_repeats":dict(unique),"unavailable_or_incomplete_coverage":True,"modules":rows,"common_failures":errors.most_common(30)}
    (run/"coverage-accounting.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("modules","common_failures")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
