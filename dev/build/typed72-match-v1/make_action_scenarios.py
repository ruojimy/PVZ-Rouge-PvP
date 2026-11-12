"""Supplementary scenarios (not part of the fixed 58): player action commands, ranked rules and
the 地刺 secret charge, which no fixed scenario issues. Written to the stage's scenarios dir."""
import json
from pathlib import Path
out=Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native\build\typed72-match-v1\scenarios')
rules={"plant_start":1000,"zombie_start":1000}
def P(**k):return dict(side='plant',**k)
def Z(**k):return dict(side='zombie',**k)
acts=dict(map='家院',seed=3,durable_heroes=True,room_ticks=420,rules=rules,
  decks={'plant':['plant:向日葵','plant:豌豆射手','plant:地刺','plant:坚果','secret:地刺','secret:闪现','secret:转向'],
         'zombie':['zombie:脑光墓碑','zombie:普通僵尸','zombie:路障僵尸','zsecret:解除封印','zsecret:起床！','zsecret:自爆']},
  inputs={
   '0':[P(type='deploy',card='plant:向日葵',x=2088,y=840),Z(type='deploy',card='zombie:脑光墓碑',x=-264,y=744)],
   '2':[P(type='deploy',card='plant:豌豆射手',x=2184,y=840)],
   '4':[P(type='deploy',card='plant:地刺',x=2232,y=840)],
   '6':[P(type='deploy',card='plant:地刺',x=2280,y=840)],
   '8':[P(type='turn',target='u3',facing=-1)],
   '10':[Z(type='select_grave',grave='$grave')],
   '12':[Z(type='deploy',card='zombie:普通僵尸',x=-264,y=744,grave='$grave')],
   '14':[P(type='teleport',target='u1')],
   '20':[P(type='mark')],
   '22':[P(type='cannon_cancel')],
   '30':[P(type='shovel',x=2184,y=816)],
   '32':[P(type='shovel',x=2088,y=816,right=True)],
   '40':[Z(type='teleport',target='$grave')],
   '60':[Z(type='detonate',target='u6')],
   '62':[Z(type='detonate',target='u7')],
   '90':[Z(type='wake',grave='$grave')],
   '200':[P(type='teleport',target='u1'),Z(type='teleport',target='$grave')]})
ranked=dict(map='家院',seed=3,durable_heroes=True,room_ticks=120,rules=dict(rules,ranked=True),
  decks={'plant':['plant:向日葵','plant:豌豆射手','plant:黄金蓓蕾'],'zombie':['zombie:脑光墓碑','zombie:普通僵尸']},
  inputs={'0':[P(type='deploy',card='plant:向日葵',x=2088,y=840),Z(type='deploy',card='zombie:脑光墓碑',x=-264,y=744)],
          '2':[P(type='deploy',card='plant:豌豆射手',x=1800,y=336),Z(type='deploy',card='zombie:脑光墓碑',x=120,y=912)],
          '4':[P(type='deploy',card='plant:黄金蓓蕾',x=1944,y=336),P(type='deploy',card='plant:黄金蓓蕾',x=1752+48*6,y=336)],
          '30':[P(type='collect',resource='$sun')]})
for name,s in (('supp_actions',acts),('supp_ranked',ranked)):
    (out/(name+'.json')).write_text(json.dumps(s,ensure_ascii=False),encoding='utf8');print(name)
