"""Mode-coverage scenarios derived from existing ones (originals unchanged):
  coop_long       coop_waves for 140 s: CoopCycle day->night at 120 s, night graves, rotation, diversion
                  (the scenario "night" key edits the map after its checksum and is rejected by V, so night is reached by time)
  coop_day10      coop_waves on campaign day 10: later tiers, larger budgets, more fronts
  pve_solo        coop_waves as solo PvE (plant seat only; plant2 inputs removed), day 6
  duel_deathmatch duel_settle_1 with deathmatch at 10 s (water, producer limits, rates)"""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
coop=json.loads((ROOT/'tools/scenarios/coop_waves.json').read_text(encoding='utf-8'))
duel=json.loads((HERE/'scenarios/duel_settle_1.json').read_text(encoding='utf-8'))
out={}
s=copy.deepcopy(coop);s['room_ticks']=4200;out['coop_long']=s
s=copy.deepcopy(coop);s['director']=dict(s['director'],day=10);s['room_ticks']=1500;out['coop_day10']=s
s=copy.deepcopy(coop);s['mode']='pve';s['director']=dict(s['director'],day=6);s['room_ticks']=1500
s['inputs']={k:[e for e in v if e.get('side')!='plant2'] for k,v in s['inputs'].items()}
s['inputs']={k:v for k,v in s['inputs'].items() if v};out['pve_solo']=s
s=copy.deepcopy(duel);s['rules']=dict(s.get('rules',{}),deathmatch_seconds=10.);out['duel_deathmatch']=s
for name,scenario in out.items():(HERE/'scenarios'/(name+'.json')).write_text(json.dumps(scenario,ensure_ascii=False),encoding='utf-8')
print(','.join(out))
