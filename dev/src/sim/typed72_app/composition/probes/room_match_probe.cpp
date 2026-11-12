#define PVZ72_ROOM_PROBE_EMBEDDED
#include "room_probe.cpp"
#include "sim/typed/room_match_control.h"
namespace {
const char* phase_name(RoomPhase p){static constexpr const char* names[]={"config","banning","picking","loading","battle","result"};return names[int(p)];}
RoomPhase match_phase(const std::string& name){for(int i=0;i<6;++i)if(name==phase_name(RoomPhase(i)))return RoomPhase(i);throw std::invalid_argument("invalid fixture phase");}
const char* settlement_name(RoomSettlementReason p){static constexpr const char* names[]={"hero_death","waves_cleared","surrender","leave","kick","disconnect","host_closed","load_timeout"};return names[int(p)];}
J settlement(const RoomSettlement& r){J out={{"winner",r.winner?J(*r.winner==RoomWinner::plant?"plant":*r.winner==RoomWinner::zombie?"zombie":"draw"):J(nullptr)},{"reason",settlement_name(r.reason)},{"tick",r.tick}};if(r.forfeit)out["forfeit"]=seat_name(*r.forfeit);if(r.pve_day)out["pve_day"]=*r.pve_day;if(r.coins)out["coins"]=*r.coins;if(r.fallen)out["fallen"]=*r.fallen;return out;}
template<class T>InputField<T> match_field(const J& op,const char* key){InputField<T> out;const auto it=op.find(key);if(it==op.end())return out;const bool valid=std::is_same_v<T,bool>?it->is_boolean():it->is_number_integer()&&!it->is_boolean();if(valid){out.state=InputFieldState::value;out.value=it->get<T>();}else out.state=it->is_null()?InputFieldState::null:InputFieldState::invalid;return out;}
struct MatchFixture:RoomProbe,RoomMatchServices {
    RoomMatchState match;RoomInputGateway gateway{inputs};RoomMatchBattle match_battle{room,room_rules,scheduler,gateway};RoomMatchControl control{match,*this};
    bool match_seen=false;std::string log_error;double match_clock=0.;int saves=0,closes=0,progress_syncs=0,progress_finishes=0,draft_timeouts=0;J records=J::array(),dropped_progress=J::array(),dropped_configs=J::array(),forgotten=J::array();
    explicit MatchFixture(const J& input):RoomProbe(input.value("seed",int64_t(1)),input.at("world_rules").at("width"),input.at("world_rules").value("splash",20./3.)){
        J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");configure_shooting(*this,base);battle.world_width.set(cfg.at("width"));battle.dense_planting=cfg.at("dense");battle.protection.deathmatch=cfg.at("deathmatch");rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();rules.homing_height=cfg.at("heights").get<decltype(rules.homing_height)>();collision.unit_scale=cfg.at("scale").get<decltype(collision.unit_scale)>();
    }
    std::string journal_error()const override{return log_error;}
    void record(const RoomMembershipEvent& e)override{
        static constexpr const char* names[]={"joined","reconnected","left","kicked","disconnected","disconnected_after_result","forfeit","interrupted","result","role_changed","battle"};
        J row={{"event",names[int(e.kind)]},{"clock",pvz::py::roundn(match.clock,3)},{"revision",match.revision}};
        if(!e.peer.empty())row["peer"]=e.peer;if(e.seat)row["side"]=seat_name(*e.seat);if(e.spectator){row["role"]=*e.spectator?"spectator":"player";if(*e.spectator)row["side"]=nullptr;}
        if(e.reason)row["reason"]=settlement_name(*e.reason);if(e.result)row["result"]=settlement(*e.result);
        if(e.kind==RoomMembershipEventKind::battle){row["number"]=e.match_number;row["terrain_hash"]=match.terrain_hash;row["decks"]=J::object();if(match.duo()){for(const auto s:match.seats())row["decks"][std::string(seat_name(s))]=J::array();}else{row["decks"]["plant"]=J::array();row["decks"]["zombie"]=J::array();}}
        records.push_back(std::move(row));
    }
    void save_replay()override{++saves;}void close_battle()override{++closes;}void reset_draft_fields()override{}
    void forget_seat_deck(Seat s)override{forgotten.push_back(seat_name(s));}
    void drop_progress_peer(const std::string& p)override{dropped_progress.push_back(p);}void drop_config_request(const std::string& p)override{dropped_configs.push_back(p);}
    void sync_progress()override{++progress_syncs;}void finish_progress(RoomSettlement&)override{++progress_finishes;}
    double monotonic_seconds()override{const auto now=match_clock;match_clock+=.001;return now;}void draft_timeout()override{++draft_timeouts;}
    bool extra_operation(const J& op,J& result)override{
        const auto name=op.at("op").get<std::string>();const auto peer=op.value("peer",std::string("guest"));
        if(name=="match_setup"){
            match_seen=true;const auto mode=op.value("mode",std::string("duel"));match.mode=mode=="duo"?MatchMode::duo:mode=="coop"?MatchMode::coop:mode=="pve"?MatchMode::pve:MatchMode::duel;
            match.terrain_hash="fixture-terrain";if(op.contains("members")){match.members.clear();for(const auto& pair:op["members"])match.members.push_back({pair[0],parse_seat(pair[1]),true});}
            match.ai_peers=op.value("ai",std::set<std::string>{});match.subsidy_peers=match.ai_peers;match.allow_spectators=op.value("allow",true);match.max_spectators=op.value("max_spectators",size_t(2));if(match.scripted())match.pve_day=3;control.bind(op.value("bind",true)?&match_battle:nullptr);
        }else if(name=="match_phase"){match.phase=match_phase(op.at("phase"));if(op.contains("deadline"))match.deadline=op["deadline"];if(op.contains("loading_id"))match.loading_id=op["loading_id"].is_null()?std::nullopt:std::optional<std::string>(op["loading_id"]);if(op.value("bind",false))control.bind(&match_battle);}
        else if(name=="match_connect")result=control.connect(peer,op.value("spectator",false),op.contains("seat")?std::optional<Seat>(parse_seat(op["seat"])):std::nullopt);
        else if(name=="match_role")result=control.change_role(peer,op.value("spectator",false),op.contains("seat")?std::optional<Seat>(parse_seat(op["seat"])):std::nullopt);
        else if(name=="match_disconnect")control.disconnect(peer);
        else if(name=="match_leave")control.leave(peer);
        else if(name=="match_kick")control.kick(peer);
        else if(name=="match_host_quit")control.host_quit();
        else if(name=="match_reopen")result=control.reopen();
        else if(name=="match_update")control.update(op.at("dt"));
        else if(name=="match_pause")result=control.pause(peer,match_field<int64_t>(op,"pause_epoch"),match_field<bool>(op,"paused"),match_field<bool>(op,"cancel"));
        else if(name=="match_loaded")result=control.loaded(peer,op.contains("loading_id")&&!op["loading_id"].is_null()?std::optional<std::string>(op["loading_id"]):std::nullopt,op.contains("terrain_hash")&&!op["terrain_hash"].is_null()?std::optional<std::string>(op["terrain_hash"]):std::nullopt);
        else if(name=="match_input")result=control.input(peer,op.at("payload"));
        else if(name=="match_capture")control.capture_result();
        else if(name=="match_result"){room.result=RoomResult{op.value("winner",std::string("plant"))=="plant"?RoomWinner::plant:RoomWinner::zombie,RoomResultReason::hero_death,room.tick};}
        else if(name=="match_audit")log_error=op.at("error");
        else return RoomProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override{
        RoomProbe::extra_snapshot(row);if(!match_seen)return;J members=J::object(),connected=J::object(),spectators=J::object(),ready=J::object(),confirmed=J::object(),loaded=J::object(),votes=J::array(),restarts=J::array();
        for(const auto& m:match.members){members[m.peer]=seat_name(m.seat);connected[m.peer]=m.connected;}for(const auto& p:match.spectators)spectators[p]=true;
        for(const auto s:match.seats()){auto key=std::string(seat_name(s));ready[key]=match.ready[seat_index(s)];confirmed[key]=match.confirmed[seat_index(s)];loaded[key]=match.loaded[seat_index(s)];}
        std::vector<std::string> vote_names;for(const auto s:match.pause_votes)vote_names.emplace_back(seat_name(s));std::sort(vote_names.begin(),vote_names.end());votes=vote_names;for(const auto s:match.restart_votes)restarts.push_back(seat_name(s));
        row["match"]={{"phase",phase_name(match.phase)},{"members",members},{"connected",connected},{"spectators",spectators},{"ready",ready},{"confirmed",confirmed},{"loaded",loaded},{"clock",match.clock},{"deadline",match.deadline},{"accumulator",match.accumulator},{"revision",match.revision},{"pause_epoch",match.pause_epoch},{"pause_votes",votes},{"restart_votes",restarts},{"paused",match.paused},{"disconnect_deadline",match.disconnect_deadline?J(*match.disconnect_deadline):J(nullptr)},{"result",match.result?settlement(*match.result):J(nullptr)},{"status",match.status},{"audit_error",control.audit_error()},{"loading_id",match.loading_id?J(*match.loading_id):J(nullptr)},{"match_number",match.match_number},{"snapshot_peers",control.snapshot_peers()},{"records",records},{"saves",saves},{"closes",closes},{"progress_syncs",progress_syncs},{"progress_finishes",progress_finishes},{"dropped_progress",dropped_progress},{"draft_timeouts",draft_timeouts}};
    }
};
J match_run(const J& input){MatchFixture probe(input);probe.operations(input.at("operations"));return probe.states;}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("expected input output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;while(std::getline(input,line))if(!line.empty())output<<match_run(J::parse(line)).dump()<<'\n';return input.bad()||!output?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
