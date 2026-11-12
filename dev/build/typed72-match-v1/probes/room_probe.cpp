#include "core/pymath.h"
#define PVZ72_NATIVE_TICK_PROBE_EMBEDDED
#include "native_tick_probe.cpp"
#include "sim/typed/room_scheduler.h"
#include "sim/typed/command_codec.h"

namespace {
J room_result(const RoomResult& value){
    J out={{"winner",value.winner==RoomWinner::plant?"plant":value.winner==RoomWinner::zombie?"zombie":"draw"},
        {"reason",value.reason==RoomResultReason::hero_death?"hero_death":value.reason==RoomResultReason::waves_cleared?"waves_cleared":"surrender"},{"tick",value.tick}};
    if(value.coins)out["coins"]=*value.coins;if(value.fallen)out["fallen"]=*value.fallen;return out;
}
struct RoomProbe:NativeTickProbe,RoomServices,CommandServices {
    RoomState room;
    RoomRules room_rules;
    RoomScheduler scheduler{battle,room,room_rules,tick_state,driver,recovery,economy,resources,*this};
    RoomCommands inputs{battle,room,room_rules,resources,commands,hero_flags,*this};
    RoomCommandQueue input_queue;
    J room_events=J::array(),boundary_events=J::array(),input_events=J::array();
    double measured=0.;
    bool sight_clear=true,cleared=false,observe_room=false;
    std::unordered_map<std::string,double> card_cooldowns;
    explicit RoomProbe(int64_t seed,double width,double splash):NativeTickProbe(seed,width,splash){}
    double monotonic_seconds()override{const auto value=measured;measured+=.001;return value;}
    void capture_deferred(bool value)override{boundary_events.push_back({"capture",value});}
    void cycle_step()override{boundary_events.push_back({"cycle"});}
    double card_cooldown(Seat,const std::string& key)override{return card_cooldowns.at(key);}
    std::optional<bool> copied_card_is_producer(const std::string& key)override{
        const auto it=battle.protection.cards.find(key);return it==battle.protection.cards.end()?std::nullopt:std::optional<bool>(it->second.producer);
    }
    void sync_public(bool terrain)override{boundary_events.push_back({"public",terrain});}
    void zombie_secrets_step(double elapsed)override{boundary_events.push_back({"secrets",elapsed});}
    void director_step()override{boundary_events.push_back({"director"});}
    bool director_cleared()const override{return cleared;}
    std::string native_command(Seat,const NativeCommand& c)override{return "fixture-native-"+std::to_string(int(c.kind));}
    bool mark_line_of_sight(Seat,Seat)const override{return sight_clear;}
    void input_attempt(int64_t tick,Seat seat,const CommandAttempt&,const std::string& error)override{input_events.push_back({"attempt",tick,seat_name(seat),error});}
    void input_accepted(int64_t tick,double time,Seat seat,const CommandAttempt&)override{input_events.push_back({"accepted",tick,pvz::py::roundn(time,4),seat_name(seat)});}
    void input_cleared(int64_t tick,Seat seat)override{input_events.push_back({"clear",tick,seat_name(seat)});}
    void emit(RoomEvent e)override{
        J row;
        std::visit([&](const auto& v){using T=std::decay_t<decltype(v)>;
            if constexpr(std::is_same_v<T,RoomResult>)row={{"event","result"},{"data",room_result(v)}};
            else if constexpr(std::is_same_v<T,RoomDeathmatchEvent>)row={{"event","deathmatch"},{"multiplier",v.multiplier}};
            else if constexpr(std::is_same_v<T,RoomSubsidyEvent>)row={{"event","ai_subsidy"},{"side",seat_name(v.seat)},{"amount",v.amount}};
            else if constexpr(std::is_same_v<T,RoomFallenEvent>)row={{"event","hero_fallen"},{"side",seat_name(v.seat)}};
            else if constexpr(std::is_same_v<T,RoomHelpedEvent>)row={{"event","hero_helped"},{"side",seat_name(v.seat)},{"helper",seat_name(v.helper)}};
            else if constexpr(std::is_same_v<T,RoomRevivedEvent>)row={{"event","hero_revived"},{"side",seat_name(v.seat)},{"helper",seat_name(v.helper)},{"hp",v.hp}};
            else if constexpr(std::is_same_v<T,RoomSpawnBlockedEvent>)row={{"event","spawn_blocked"},{"card",v.card},{"reason","deathmatch_pending_copy"}};
            else if constexpr(std::is_same_v<T,RoomRallyEvent>)row={{"event","rally"},{"side",seat_name(v.seat)},{"point",v.point?J{{"x",v.point->x},{"y",v.point->y}}:J(nullptr)}};
            else if constexpr(std::is_same_v<T,RoomCommandEvent>)row={{"event","command"},{"side",seat_name(v.seat)},{"mode",v.mode==PathMode::follow_hero?"follow":"attack"},{"seq",v.sequence}};
            else if constexpr(std::is_same_v<T,RoomGiftEvent>)row={{"event","gift"},{"side",seat_name(v.seat)},{"to",seat_name(v.to)},{"amount",v.amount}};
            else if constexpr(std::is_same_v<T,RoomSurrenderRequestEvent>)row={{"event","surrender_requested"},{"side",seat_name(v.seat)},{"request",v.request}};
            else if constexpr(std::is_same_v<T,RoomSurrenderVoteEvent>)row={{"event","surrender_vote"},{"side",seat_name(v.seat)},{"request",v.request},{"accepted",v.accepted}};
        },e);room_events.push_back(std::move(row));
    }
    bool extra_operation(const J& op,J& result)override{
        const auto name=op.at("op").get<std::string>();
        if(name=="room_setup"){
            observe_room=true;room_rules.tick_rate=op.value("rate",30);room_rules.deathmatch_seconds=op.value("deathmatch",180.);
            room_rules.production_multiplier=2.;room_rules.recovery={10.,1.,1.,false};room_rules.economy=economy_rules;
            room_rules.hero_lock_range=360.;room_rules.mark_seconds=6.;room.capture_demand=op.value("capture",false);
            room.director=op.value("director",false);room.director_cycle=op.value("cycle",false);room.zombie_secrets=op.value("secrets",false);
            room.tick=op.value("tick",int64_t(0));world.time=room.tick*room_rules.dt();room.native_phase=op.value("phase",0);
            room.ai_subsidy_paid=op.value("paid",int64_t(0));room.ai_subsidy_seats.clear();
            for(const auto& s:op.value("subsidy",J::array()))room.ai_subsidy_seats.push_back(parse_seat(s.get<std::string>()));
            for(size_t i=0;i<world.heroes.size();++i)if(world.heroes[i]){
                auto& h=*world.heroes[i];h.previous_hp.set(h.frame.hp.get());h.last_damage.set(0.);h.regen_progress.set(0.);
                auto& p=*world.players[i];p.height=battle.runtime.tile*1.9;room.players[i].last_input_tick=room.tick;
            }
        }else if(name=="room_input")result=inputs.apply(parse_seat(op.at("side").get<std::string>()),decode_command(op.at("payload")));
        else if(name=="room_clear")inputs.clear(parse_seat(op.at("side").get<std::string>()));
        else if(name=="room_step")scheduler.step(op.value("count",int64_t(1)));
        else if(name=="room_player"){
            const auto side=parse_seat(op.at("side").get<std::string>());const auto i=seat_index(side);auto& p=world.players[i].value();auto& s=room.players[i];
            if(op.contains("seq"))s.sequence=op.at("seq");if(op.contains("last"))s.last_input_tick=op.at("last");
            if(op.contains("hp")){p.hp=op.at("hp");world.heroes[i]->frame.hp.set(p.hp);}
            if(op.contains("presses"))p.jump_presses=op.at("presses");if(op.contains("revive"))room.revive[i]=op.at("revive");
            if(op.contains("lock"))s.collect_locked_until=op.at("lock");
            if(op.contains("cooldowns"))p.cooldowns=op.at("cooldowns").get<decltype(p.cooldowns)>();
            if(op.contains("spans"))s.cooldown_spans=op.at("spans").get<decltype(s.cooldown_spans)>();
            if(op.contains("native"))read_hero(op.at("native"),world.heroes[i].value());
            if(op.contains("position")){p.position=point(op.at("position"));auto& pos=*world.heroes[i]->frame.position.get();pos.x=p.position.x;pos.y=p.position.y;}
        }else if(name=="room_card")card_cooldowns[op.at("id").get<std::string>()]=op.at("cooldown");
        else if(name=="room_state"){
            if(op.contains("audit"))room.audit_error=op.at("audit");if(op.contains("cleared"))cleared=op.at("cleared");
            if(op.contains("sight"))sight_clear=op.at("sight");if(op.contains("intermediate"))room.capture_intermediate=op.at("intermediate");
        }else return NativeTickProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override{
        NativeTickProbe::extra_snapshot(row);if(!observe_room)return;
        J players=J::object();for(size_t i=0;i<world.players.size();++i)if(world.players[i]){
            const auto& p=*world.players[i];const auto& s=room.players[i];
            players[std::string(seat_name(Seat(i)))]={{"seq",s.sequence},{"last",s.last_input_tick},{"move",p.move},{"held",p.jump_held},{"presses",p.jump_presses},
                {"reported",s.press_reported},{"immune",s.immune_until},{"gift_ready",s.gift_ready_at},{"cooldowns",p.cooldowns},{"spans",s.cooldown_spans},{"revive",room.revive[i]},
                {"down",room.down_since[i]?J(*room.down_since[i]):J(nullptr)}};
        }
        J requests=J::array();for(const auto& r:room.surrender_requests)requests.push_back(r?J{{"id",r->id},{"seat",seat_name(r->seat)},{"expires",r->expires}}:J(nullptr));
        row["room"]={{"tick",room.tick},{"time",world.time},{"phase",room.native_phase},{"deathmatch",room.deathmatch},
            {"defer",room.defer_capture},{"frames",room.capture_frames},{"deferred",room.capture_deferred},{"cost",room.native_cost_ratio?J(*room.native_cost_ratio):J(nullptr)},
            {"result",room.result?room_result(*room.result):J(nullptr)},{"players",players},{"paid",room.ai_subsidy_paid},{"fallen",room.fallen_count},
            {"events",room_events},{"boundaries",boundary_events},{"inputs",input_events},{"requests",requests}};
    }
};
J run_room(const J& input){
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    RoomProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_ROOM_PROBE_EMBEDDED
int main(int argc,char** argv){
    try{if(argc!=3)throw std::invalid_argument("usage: room72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);if(!input||!output)throw std::runtime_error("room fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_room(J::parse(line)).dump()<<'\n';return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
