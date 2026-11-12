#include "sim/typed/ai_plant_placement.h"
#include "sim/typed/command_codec.h"
#include "sim/typed/room_wire.h"
#include <fstream>
#include <iostream>
using namespace pvz::typed72;
namespace {
#include "ai_probe_fixture.inc"
struct PlacementServices:AiTacticalServices {
    std::unordered_map<std::string,AiDeckCardView> cards;const J* operation=nullptr;J sent=J::array(),previewed=J::array();uint64_t resets=0;
    const AiDeckCardView& card(const std::string& key)override{return cards.at(key);}
    std::string send(Seat side,CommandPayload payload)override{auto raw=encode_generated_command(0,payload);raw.erase("seq");raw["side"]=seat_name(side);sent.push_back(std::move(raw));const auto& command=std::get<NativeCommand>(payload);return operation->value("send_errors",J::object()).value(command.card.value,std::string{});}
    AiPlacementResult preview(Seat side,const std::string& key,Point p,const std::optional<std::string>& grave)override{previewed.push_back(J::array({seat_name(side),key,p.x,p.y,grave?J(*grave):J(nullptr)}));return {operation->value("preview_errors",J::object()).value(key,std::string{}),operation->value("placement",true)};}
    void reset_preview()override{++resets;}
};
J run_placement(const J& input){
    PlacementServices services;AiTacticalState state;AiPlantPlacementState places;AiFiringFailures failures;AiPlantPlacement controller(state,places,failures);
    for(const auto& [key,value]:input.at("cards").items()){AiDeckCardView c;c.id=key;c.name=value.value("name",std::string{});c.behavior=value.value("behavior",std::string{});c.cost=value.value("cost",0.);c.cooldown_ready=value.value("cooldown",0.);c.range=optional_value<double>(value,"range");c.producer=value.value("producer",false);c.mushroom=value.value("mushroom",false);c.aquatic=value.value("aquatic",false);c.lob=value.value("lob",false);c.star=value.value("star",false);c.homing=value.value("homing",false);services.cards.emplace(key,std::move(c));}
    J output=J::array();for(const auto& op:input.at("operations")){
        services.operation=&op;TargetSight sight;RoomPublicTerrain terrain;for(const auto& row:op.at("tiles")){std::vector<uint8_t> solid,water;std::vector<RoomPublicCell> tiles;for(const auto& raw:row){RoomPublicCell cell;cell.kind=raw.value("kind",std::string{});cell.water=raw.value("water",false);cell.solid=raw.value("solid",false);solid.push_back(cell.solid);water.push_back(cell.water);tiles.push_back(std::move(cell));}sight.solid.push_back(std::move(solid));sight.water.push_back(std::move(water));terrain.tiles.push_back(std::move(tiles));}
        const double tile=op.value("tile",48.),width=op.value("width",960.);AiField field(sight,width,terrain.tiles.size()*tile,tile);const auto me=public_hero(op.at("me")),foe=public_hero(J::object());auto units=public_units(op.value("units",J::array()));std::vector<AiFiringTarget> targets;for(const auto& u:op.value("units",J::array()))if(u.value("side",std::string{})=="zombie"&&u.value("hp",0.)>0.)targets.push_back({point(u),u.value("h",0.)});AiFiringFrame firing_frame{sight,targets,width,tile};AiFiring firing(firing_frame);
        AiTacticalFrame frame{.me=me,.foe=foe,.terrain=sight,.field=field};frame.width=width;frame.tile=tile;frame.time=op.value("time",0.);frame.units=units;frame.deathmatch=op.value("deathmatch",false);frame.owner=seat_value(input.value("owner",J("plant")));AiTacticalContext context(frame,services);
        std::vector<AiObservedTarget> supports;for(const auto& raw:op.value("empty_supports",J::array())){AiObservedTarget s;s.position=point(raw);s.plant_y=raw.at("plant_y");supports.push_back(s);}auto deck=op.at("me").value("deck",std::vector<std::string>{});auto secrets=op.at("me").value("secrets",std::vector<std::string>{});AiPlantPlacementFrame placement{deck,secrets,supports,terrain,firing};
        auto result=controller.place_at(context,placement,op.at("card"),{op.at("x"),op.at("y")},op.value("facing",1));J dead=J::array(),bad=J::array();for(const auto& [cell,until]:places.dead_spots)dead.push_back({cell.first,cell.second,until});for(const auto& b:places.bad_pot_ground)bad.push_back({b.pot?J(*b.pot):J(nullptr),b.top?J(*b.top):J(nullptr),b.lift});
        output.push_back({{"result",result},{"sent",services.sent},{"previewed",services.previewed},{"resets",services.resets},{"failed",state.failed},{"log",state.log},{"dead_spots",dead},{"bad_ground",bad},{"lane_count",failures.entries.size()},{"lane_blocked",failures.lane_blocked},{"last_blocked_card",failures.last_blocked_card}});
    }return output;
}
}
int main(int argc,char** argv){try{if(argc!=3)throw std::invalid_argument("expected input output");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);std::string line;while(std::getline(in,line))if(!line.empty())out<<run_placement(J::parse(line)).dump()<<'\n';return in.bad()||!out?2:0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
