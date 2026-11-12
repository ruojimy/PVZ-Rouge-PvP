"""Generate 1v1 scenarios that play to a hero death.  Default rules, real HP."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent/'scenarios';HERE.mkdir(exist_ok=True)
def duel(seed,room_ticks,zombie_col,plant_col,row,walk=60):
    tile=48;inputs={}
    def add(t,**cmd):inputs.setdefault(str(t),[]).append(cmd)
    # Plant side: economy and defence around its own hero.
    for i,t in enumerate((0,90,300,600,900)):
        add(t,side='plant',type='deploy',card='plant:向日葵' if i%2==0 else 'plant:豌豆射手',x=(plant_col+2+i)*tile+24,y=(row+1)*tile-24)
    # Zombie side: graves near its hero, then soldiers from them for the whole match.
    for i,t in enumerate((0,120,420,800)):
        add(t,side='zombie',type='deploy',card='zombie:脑光墓碑',x=(zombie_col-2-i)*tile+24,y=(row+1)*tile-24)
    for t in range(150,room_ticks,75):
        add(t,side='zombie',type='deploy',card='zombie:普通僵尸',x=(zombie_col+1)*tile+24,y=(row+1)*tile-24,grave='$grave')
    # Heroes also walk toward each other from time to time.
    # The horde follows its hero, so the zombie hero walks to the plant hero and stays.
    add(200,side='zombie',type='move',move=1,jump=False);add(200+walk,side='zombie',type='move',move=0,jump=False)
    return dict(map='家院',seed=seed,weather='clear',durable_heroes=False,room_ticks=room_ticks,
        place=dict(zombie=[zombie_col,row],plant=[plant_col,row]),setup=[dict(op='command',value='follow')],inputs=inputs)
for name,s in {'duel_settle_1':duel(7,4000,36,50,17)}.items():
    (HERE/(name+'.json')).write_text(json.dumps(s,ensure_ascii=False),encoding='utf8')
print('ok')
