"""native_battle._team_step (native_battle.py:2548-2552): a scripted (coop/pve) result also carries
coins and fallen, in battle.result and the emitted result event. RoomResult already holds them
(room_scheduler.cpp:87); the driver's event and final-result serialization dropped them (coop_long)."""
from pathlib import Path
p=Path(__file__).with_name('match_probe.cpp');t=p.read_text(encoding='utf8')
if 'scripted_result_fields' in t:raise SystemExit('already patched')
def sub(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a)
    t=t.replace(a,b)
sub('''            if constexpr(std::is_same_v<T,RoomResult>)log_event({{"event","result"},{"winner",v.winner==RoomWinner::plant?"plant":v.winner==RoomWinner::zombie?"zombie":"draw"},{"reason",v.reason==RoomResultReason::hero_death?"hero_death":v.reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"}});''',
'''            if constexpr(std::is_same_v<T,RoomResult>){J row{{"event","result"},{"winner",v.winner==RoomWinner::plant?"plant":v.winner==RoomWinner::zombie?"zombie":"draw"},{"reason",v.reason==RoomResultReason::hero_death?"hero_death":v.reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"}};
                scripted_result_fields(row,v);log_event(row);}''')
sub('''            if(match.room.result)result={{"winner",match.room.result->winner==RoomWinner::plant?"plant":match.room.result->winner==RoomWinner::zombie?"zombie":"draw"},{"reason",match.room.result->reason==RoomResultReason::hero_death?"hero_death":match.room.result->reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",match.room.result->tick}};''',
'''            if(match.room.result){result={{"winner",match.room.result->winner==RoomWinner::plant?"plant":match.room.result->winner==RoomWinner::zombie?"zombie":"draw"},{"reason",match.room.result->reason==RoomResultReason::hero_death?"hero_death":match.room.result->reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",match.room.result->tick}};
                MatchProbe::scripted_result_fields(result,*match.room.result);}''')
sub('    static J poison_v(const PoisonSlot& slot){','''    // Scripted results carry the campaign coins and the fallen-Dave count.
    static void scripted_result_fields(J& row,const RoomResult& r){if(r.coins)row["coins"]=*r.coins;if(r.fallen)row["fallen"]=*r.fallen;}
    static J poison_v(const PoisonSlot& slot){''')
p.write_text(t,encoding='utf8');print('ok')
