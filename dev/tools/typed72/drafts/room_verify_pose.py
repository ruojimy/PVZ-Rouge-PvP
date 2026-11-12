"""Full native_pose at the real _sync_public boundary, including detachment."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import room_verify_public as base
source_cases=base.cases
NUMBERS=['二段跳','玩家倒地','气球','冻水','speedmax','dushu','speed','wjx','wjy','玩家恢复','玩家受伤','xx','yy','猫尾','猫尾cd','猫尾摇摆','citoux','toudushu','辣飞天','__pvz_sb_chili_launch_lock_until']
SCALARS=['_pvp_max_hp','_pvp_stun','_pvp_last_damage','_pvp_regen_progress','_pvp_pea_angle','native_ticks','_pvp_balloon_hp','_pvp_previous_hp','_pvp_water_damage_clock','_pvp_masochist_ready']
FLAGS=['玩家入水','入水','sbs','_pvp_sturdy_down','_pvp_floating_body','_pvp_rally_before','_pvp_rally_eligible','_pvp_rally_checked']
TOKENS=[None,'','source:中文\n\t\x00\\\"\'羽',[True,False,-7,{'tuple':['inner',None]}],{'tuple':['native:source',12345]}, {'tuple':[]},9223372036854775807,-9223372036854775808]
def cases():
    result=[]
    for i,c in enumerate(source_cases()):
        c=copy.deepcopy(c);c['include_native_pose']=True
        for j,(seat,h) in enumerate(c['heroes'].items()):
            for k,key in enumerate(NUMBERS):h[key]=(i*3+j+k)/8.
            for k,key in enumerate(SCALARS):h[key]=i*5+j+k
            for k,key in enumerate(FLAGS):h[key]=(j+k+i)%2==0
            h.update({'模式':'我是僵尸' if seat.startswith('zombie') else '正常模式','玩家皮肤':'中文皮肤','秘籍':['蓝火','猫尾'],'_pvp_owner':'zombie' if seat.startswith('zombie') else 'plant','_pvp_id':'hero:'+seat,'_pvp_seat':seat,'_pvp_launch_attack':copy.deepcopy(TOKENS[(i+j)%len(TOKENS)])})
            h['_pvp_poison']={'level':j,'until':20.,'next':1.,'owner':'plant2','layers':{'2':{'until':30.,'next':2.,'owner':'zombie2'},'1':{'until':40.,'next':3.,'owner':'plant'}}}
            if i%3==0:
                for key in NUMBERS[::4]+SCALARS[::4]+FLAGS[::4]:h.pop(key,None)
            elif i%3==1:
                for key in NUMBERS[::5]+SCALARS[::5]+FLAGS[::5]:h[key]=None
            if i%4==0:h['_pvp_poison'].pop('layers')
            if i%4==1:h['_pvp_poison']['layers']=None
        # Mutate the original lists/source/layer after publication; the prior
        # native_pose must remain detached until the next publication.
        c['heroes']['plant']['_pvp_poison']['layers']={'2':{'until':30.,'next':2.,'owner':'zombie2'}}
        c['operations'].insert(1,dict(hero_mutate='plant',publish=False))
        c['operations'].insert(2,dict(publish=True))
        # Existing cases also replace an avatar with a sparse source record:
        # that checks stale optional fields really disappear at publication.
        result.append(c)
    return result
if __name__=='__main__':
    base.cases=cases;base.extra_paths=[Path(__file__).resolve()]
    raise SystemExit(base.main())
