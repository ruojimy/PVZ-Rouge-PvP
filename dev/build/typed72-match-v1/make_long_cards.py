"""Long card-coverage scenarios: the generated cards_* setups (tools/gen_card_scenarios.py) run for
360 room ticks (12 s, ~3000 native ticks) instead of 72, so effects that need time to resolve
(production, grave consumption, cart expiry, echo summons, poison, secrets) are compared too.
Originals in tools/scenarios stay unchanged; outputs go to this stage's scenarios/long_*.json."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'tools'/'scenarios';OUT=Path(__file__).resolve().parent/'scenarios'
ROOM_TICKS=int(sys.argv[1]) if len(sys.argv)>1 else 360
names=[]
for path in sorted(SRC.glob('cards_*.json')):
    scenario=json.loads(path.read_text(encoding='utf-8'))
    scenario['room_ticks']=ROOM_TICKS
    name='long_'+path.stem;names.append(name)
    (OUT/(name+'.json')).write_text(json.dumps(scenario,ensure_ascii=False),encoding='utf-8')
print(','.join(names))
