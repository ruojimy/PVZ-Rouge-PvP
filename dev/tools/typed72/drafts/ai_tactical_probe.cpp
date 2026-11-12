#include "sim/typed/ai_tactical_base.h"
#include "sim/typed/ai_human_prior.h"
#include "sim/typed/room_wire.h"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
namespace {
#include "ai_probe_fixture.inc"
struct Services:AiTacticalServices {
    J sent=J::array();std::string error,placement_error;bool placement=true;size_t previews=0,resets=0;
    std::unordered_map<std::string,AiDeckCardView> cards;
    std::string send(Seat seat,CommandPayload payload)override{
        J data={{"side",fixture_seat_name(seat)}};
        if(const auto* move=std::get_if<MoveCommand>(&payload)){data["type"]="move";data["move"]=move->move.value;data["jump"]=move->jump.value;data["edge"]=move->edge;}
        else {const auto& d=std::get<NativeCommand>(payload);data["type"]="deploy";data["card"]=d.card.value;data["x"]=d.x.value;data["y"]=d.y.value;data["grave"]=d.grave.valid()?J(d.grave.value):J(nullptr);data["facing"]=d.facing.value;}
        sent.push_back(data);return error;
    }
    const AiDeckCardView& card(const std::string& key)override{return cards.at(key);}
    AiPlacementResult preview(Seat,const std::string&,Point,const std::optional<std::string>&)override{++previews;return {placement_error,placement};}
    void reset_preview()override{++resets;}
};
J state_json(const AiTacticalState& s,const Services& services){
    J route=nullptr;if(s.ladder_route){const auto& r=*s.ladder_route;route={{"col",r.column},{"x",r.x},{"goal_y",r.goal_y},{"up",r.up},{"until",r.until},{"progress_at",r.progress_at},{"y",r.y}};if(r.engaged)route["engaged"]=true;}
    return {{"jump_down",s.jump_down},{"blocked",s.blocked},{"next_jump",s.next_jump},{"last_pos",s.last_position?J::array({s.last_position->first,s.last_position->second}):J(nullptr)},{"stuck_since",s.stuck_since?J(*s.stuck_since):J(nullptr)},{"detour_until",s.detour_until},{"failed",s.failed},{"log",s.log},{"ladder_route",route},{"ladder_backoff_until",s.ladder_backoff_until},{"sent",services.sent},{"previews",services.previews},{"resets",services.resets}};
}
J run(const J& c){
    if(c.at("kind")=="human_prior"){J result=J::array();for(const auto& deck:c.at("decks"))result.push_back(ai_human_feature(deck.get<std::vector<std::string>>()));return result;}
    TargetSight sight;std::vector<std::vector<uint8_t>> ladders;
    for(const auto& row:c.at("tiles")){std::vector<uint8_t> solid,water,ladder;for(const auto& cell:row){solid.push_back(cell.value("solid",false));water.push_back(cell.value("water",false));const auto kind=cell.value("kind",std::string{});ladder.push_back(cell.value("ladder",false)||kind=="梯子块"||kind=="梯子"||kind=="扶梯");}sight.solid.push_back(solid);sight.water.push_back(water);ladders.push_back(ladder);}
    const double width=c.value("width",3456.),tile=c.value("tile",48.);AiField field(sight,width,sight.solid.size()*tile,tile);Services services;AiTacticalState state;AiTacticalBase controller(state);J result=J::array();
    if(c.contains("cards"))for(const auto& [key,value]:c["cards"].items()){AiDeckCardView card;card.id=key;card.cost=value.value("cost",0.);card.cooldown_ready=value.value("cooldown",0.);card.producer=value.value("producer",false);services.cards.emplace(key,card);}
    for(const auto& op:c.at("operations")){
        const auto me=public_hero(op.at("me")),foe=public_hero(op.value("foe",J::object()));auto units=public_units(op.value("units",J::array()));std::vector<AiObservedThreat> threats;
        for(const auto& t:op.value("threats",J::array())){AiObservedThreat threat;threat.eta_ms=t.value("eta_ms",int64_t(9999));threat.projectile=t.value("source",std::string{})=="projectile";threats.push_back(threat);}
        AiTacticalFrame frame{.me=me,.foe=foe,.terrain=sight,.field=field};frame.width=width;frame.tile=tile;frame.ladders=ladders;frame.units=units;frame.threats=threats;frame.time=op.value("time",0.);frame.side=faction(c.value("side",J("plant")));frame.owner=c.contains("owner")?seat_value(c["owner"]):frame.side;
        const auto mode=op.value("mode",std::string("duo"));frame.mode=mode=="duo"?AiTeamMode::duo:mode=="coop"?AiTeamMode::coop:mode=="pve"?AiTeamMode::pve:AiTeamMode::duel;frame.deathmatch=op.value("deathmatch",false);AiTacticalContext context(frame,services);
        if(op.contains("recovering"))state.recovering=op["recovering"];if(op.contains("hold_until"))state.hold_refuge_until=op["hold_until"].is_null()?std::nullopt:std::optional<double>(op["hold_until"].get<double>());
        services.error=op.value("send_error",std::string{});services.placement_error=op.value("placement_error",std::string{});services.placement=op.value("placement",true);
        J value;const auto kind=op.at("op");
        if(kind=="drive")value=controller.drive(context,op.at("target"),op.value("jump_wish",false),op.value("tolerance",20.));
        else if(kind=="deploy")value=controller.try_deploy(context,op.at("card"),{op.at("x"),op.at("y")},optional_value<std::string>(op,"grave"),op.value("facing",1));
        else if(kind=="ready")value=context.ready(op.at("card"),op.value("reserve",0.));
        else if(kind=="spots"){value=J::array();for(const auto& spot:context.spots(op.value("free",true)))value.push_back({spot.point.x,spot.point.y,spot.water});}
        else if(kind=="ladder"){
            std::optional<AiSupportReason> reason;if(op.contains("reason"))for(size_t i=0;i<20;++i)if(ai_support_reason_name(AiSupportReason(i))==op["reason"].get<std::string>())reason=AiSupportReason(i);
            const auto move=controller.ladder_drive(context,op.at("post"),op.at("goal_y"),reason);value=move?J(*move):J(nullptr);
        }else throw std::invalid_argument("unknown tactical operation");
        result.push_back({{"result",value},{"state",state_json(state,services)}});
    }return result;
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("usage: ai_tactical72_probe input output");std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);std::string line;while(std::getline(input,line))if(!line.empty())output<<run(J::parse(line)).dump()<<'\n';return input.bad()||!output?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
