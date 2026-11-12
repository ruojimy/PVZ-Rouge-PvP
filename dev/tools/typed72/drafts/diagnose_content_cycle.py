"""Recompare retained cycle output without rerunning its C++ producer."""
import importlib.util
import json
from pathlib import Path
import sys
import traceback
ROOT=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
sys.path.insert(0,str(ROOT/'tools/typed72'))
import evidence_archive
spec=importlib.util.spec_from_file_location('cycle_diagnostic',Path(__file__).with_name('verify_content_cycle.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
reference=m.base.hero.load_reference();pref=m.shooting.plants.protection.reference();extra=m.base.reference()
out=ROOT/'test_results/content_zombies_child/cycle8_v4_diagnostic'
out.mkdir(exist_ok=True)
results=[]
with evidence_archive.open_evidence(ROOT/'test_results/content_zombies_child/cycle8_v4_r2/actual.jsonl') as actual:
    for index,((label,case),line) in enumerate(zip(m.cases(),actual)):
        got=json.loads(line)
        try:
            want=m.base.hero.oracle(case,reference,lambda ctx:m.base.ContentControllersExtension(ctx,case,pref,extra))
            diff=m.shooting.difference(want,got);result=dict(case=index,passed=diff is None,difference=diff)
            if diff is not None:
                (out/('expected-%02d.json'%index)).write_text(json.dumps(want,ensure_ascii=False),encoding='utf8')
                (out/('actual-%02d.json'%index)).write_text(json.dumps(got,ensure_ascii=False),encoding='utf8')
        except Exception as error:
            traceback.print_exc();result=dict(case=index,passed=False,error=repr(error))
        print(json.dumps(result,ensure_ascii=False),flush=True);results.append(result)
(out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
