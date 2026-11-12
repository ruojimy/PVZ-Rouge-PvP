"""fixture_inventory.py: per probe layer of the match chain, the lines that are test fixture only
(JSON op handling, recorders, fixture-owned indexes and logs) versus composition (system members,
service overrides), as the starting point for flattening into a production composition."""
import json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
P=Path(__file__).resolve().parent/'probes'
CHAIN=['hero','targets','plants','doom','chili','sourced','death','service','squash','pea','shooting','world_rules','resources',
       'plant_region','flying_plants','grenadiers','content_zombies64','native_tick','native_status','content_zombies','content_controllers','content_phase']
FIXTURE=[('json_ops',re.compile(r'\b(operations|extra_operation|extra_snapshot|keys\(|op\.at\(|op\.value\(|op\.contains\(|J::array|J::object|J\{\{)')),
         ('recorders',re.compile(r'\b(record\(|before\(|after\(|calls\.push_back|render_log|_events\.push_back|states\.push_back)')),
         ('fixture_index',re.compile(r'\b(index\(|all_plants|births\.|units\.at|sources\.at|unit_index)')),
         ('entry_points',re.compile(r'^\s*J run_|^J run_|configure_[a-z_]+\('))]
rows=[]
for stem in CHAIN:
    f=P/(stem+'_probe.cpp')
    if not f.exists():rows.append({'layer':stem,'missing':True});continue
    lines=f.read_text(encoding='utf8',errors='replace').splitlines()
    counts={k:0 for k,_ in FIXTURE};fixture=0
    for line in lines:
        hit=False
        for k,rx in FIXTURE:
            if rx.search(line):counts[k]+=1;hit=True
        fixture+=hit
    structs=[m.group(1) for m in (re.match(r'^struct (\w+)\s*:',l) for l in lines) if m]
    rows.append({'layer':stem,'structs':structs,'lines':len(lines),'fixture_lines':fixture,**counts,
                 'overrides':sum('override' in l for l in lines)})
for r in rows:print(r)
out=Path(__file__).resolve().parent/'fixture_inventory.json'
out.write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf8')
print('total lines',sum(r.get('lines',0) for r in rows),'fixture lines',sum(r.get('fixture_lines',0) for r in rows))
