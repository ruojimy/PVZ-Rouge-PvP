"""Independent census checks plus the unchanged v1 feature prefix on real states."""
import argparse,json,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--encoder',type=Path,required=True);ap.add_argument('--record',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
assert not a.out.exists();a.out.mkdir()
for version in [1,2]:
    subprocess.run([str(a.encoder),str(a.out/f'v{version}.jsonl'),'-','--feature-version',str(version),str(a.record)],check=True)
def rows(p):return [json.loads(s) for s in p.read_text('utf-8').splitlines()]
v1=rows(a.out/'v1.jsonl')[1:];v2=rows(a.out/'v2.jsonl')[1:]
record_rows=rows(a.record);fields={name:i for i,name in enumerate(record_rows[0]['unit_fields'])}
plans=[r for r in record_rows if r['type']=='plan'];assert len(v1)==len(v2)==len(plans)
maximum=0.
for old,new,r in zip(v1,v2,plans):
    assert old['x']['global']==new['x']['global'][:20]
    assert all(old['x'][k]==new['x'][k] for k in ['own','enemy'])
    s=r['input'];totals=[0.]*8
    for u in s['units']:
        if u[6]<=0:continue
        own=u[2]==s['side'];behavior=u[fields['card_behavior']];producer=u[fields['card_producer']];cost_value=u[fields['card_cost']];basic=behavior in ['shoot','reed61','flying56']
        if own:
            totals[0]+=producer;totals[1]+=basic;totals[2]+=basic or behavior in ['mortar','spring'];totals[3]+=basic or behavior=='mortar'
        if not producer:totals[6 if own else 7]+=cost_value if cost_value is not None else 0
        dx=abs((u[4]-s['me']['x']+s['width']/2)%s['width']-s['width']/2);dy=abs(u[5]-s['me']['y'])
        if not own and u[12]:
            cost=cost_value if cost_value is not None else 25
            if dx<350 and dy<200:totals[4]+=cost
            if dx<500 and dy<250:totals[5]+=cost
    expected=[v/scale for v,scale in zip(totals,[10,10,10,10,500,500,1000,1000])]
    error=max(abs(x-y) for x,y in zip(expected,new['x']['global'][20:]));maximum=max(maximum,error)
    assert error<1e-12
bad=subprocess.run([str(a.encoder),str(a.out/'bad-version.jsonl'),'-','--feature-version','99',str(a.record)],capture_output=True)
assert bad.returncode!=0
report=dict(passed=True,states=len(plans),v1_prefix_unchanged=True,census_max_error=maximum,invalid_schema_rejected=True)
(a.out/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))
