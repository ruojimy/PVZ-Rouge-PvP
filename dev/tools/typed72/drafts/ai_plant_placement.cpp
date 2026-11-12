#include "sim/typed/ai_plant_placement.h"
#include "core/pymath.h"
#include <algorithm>
#include <cmath>
namespace pvz::typed72 {
namespace {
bool has(std::span<const std::string> values,const std::string& key){return std::find(values.begin(),values.end(),key)!=values.end();}
bool one_of(const std::string& value,std::initializer_list<const char*> choices){return std::find(choices.begin(),choices.end(),value)!=choices.end();}
std::optional<std::string> ground_kind(const RoomPublicCell* p){return p?std::optional<std::string>(p->kind):std::nullopt;}
}
const RoomPublicCell* AiPlantPlacement::ground(const AiTacticalContext& c,const AiPlantPlacementFrame& f,Point point){
    const auto row=int64_t(py::floordiv(point.y+2.,c.frame.tile));const auto col=size_t(py::floordiv(py::mod(point.x,c.frame.width),c.frame.tile));
    return row>=0&&size_t(row)<f.terrain.tiles.size()?&f.terrain.tiles[size_t(row)].at(col):nullptr;
}
std::optional<int> AiPlantPlacement::direction(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    const auto& card=c.services.card(key);const AiFiringCard firing{card.id,card.name,card.behavior,card.range,card.producer,card.lob,card.star,card.homing};
    const auto blocked=failures_.blocked_lane_count,turned=failures_.turn_count;
    auto result=failures_.direction(f.firing,firing,point,facing,c.frame.time,c.frame.width,c.frame.tile);
    if(failures_.blocked_lane_count!=blocked)state_.log["skip:blocked_firing_lane"]+=double(failures_.blocked_lane_count-blocked);
    if(failures_.turn_count!=turned)state_.log["route_replan:turn"]+=double(failures_.turn_count-turned);
    return result;
}
std::string AiPlantPlacement::try_deploy(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,std::optional<std::string> grave,int facing){
    const auto heading=direction(c,f,key,point,facing);if(!heading)return "blocked firing lane";return base_.try_deploy(c,key,point,std::move(grave),*heading);
}
std::string AiPlantPlacement::place_at(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    if(c.services.card(key).aquatic&&has(f.deck,"plant:水盆")){
        for(const auto* u:c.own)if(u->card=="plant:水盆"&&std::abs(ai_wrap_delta(u->position.x,point.x,c.frame.width))<c.frame.tile*.6&&std::abs(u->position.y-point.y)<c.frame.tile)return try_deploy(c,f,key,{u->position.x,u->position.y-c.frame.tile*.5},{},facing);
        const auto* cell=ground(c,f,point);if(c.ready("plant:水盆")&&(!cell||!cell->water)){
            if(try_deploy(c,f,"plant:水盆",point,{},facing).empty()){++state_.log["basin70"];return {};}
        }
    }
    const auto heading=direction(c,f,key,point,facing);if(!heading)return "blocked firing lane";return place18(c,f,key,point,*heading);
}
std::string AiPlantPlacement::place18(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    auto error=place11(c,f,key,point,facing);
    if(!error.empty()&&error.find("此处不符合原版种植条件")!=std::string::npos&&!one_of(c.services.card(key).behavior,{"pot","lily"})&&has(f.deck,"plant:花盆")&&c.ready("plant:花盆")){
        if(try_deploy(c,f,"plant:花盆",point,{},facing).empty()){++state_.log["pot_for_native_rule"];return {};}
    }
    return error;
}
std::string AiPlantPlacement::place11(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    const auto cell=std::pair(int64_t(py::floordiv(py::mod(point.x,c.frame.width),c.frame.tile*.5)),int64_t(py::floordiv(point.y,c.frame.tile*.5)));
    const auto previous=places_.dead_spots.find(cell);if(previous!=places_.dead_spots.end()&&previous->second>c.frame.time){++state_.log["dead_spot_skip"];return "memo";}
    const auto nearby=[&](const AiObservedTarget& s){return std::abs(ai_wrap_delta(s.position.x,point.x,c.frame.width))<c.frame.tile*.6&&std::abs(s.position.y-point.y)<c.frame.tile;};
    const auto& behavior=c.services.card(key).behavior;
    if(!places_.bad_pot_ground.empty()&&!one_of(behavior,{"pot","lily","spike"})){
        const auto here=ground_kind(ground(c,f,point));for(const auto& bad:places_.bad_pot_ground)if(here==bad.pot&&ground_kind(ground(c,f,{point.x,point.y-bad.lift}))==bad.top&&std::none_of(f.empty_supports.begin(),f.empty_supports.end(),nearby)){++state_.log["bad_pot_ground_skip"];return "memo";}
    }
    auto error=place65(c,f,key,point,facing);
    if(error.find("原版种植条件")!=std::string::npos)for(const auto& s:f.empty_supports)if(nearby(s)){
        places_.dead_spots[cell]=c.frame.time+120.;AiPlantPlacementState::BadGround bad{ground_kind(ground(c,f,s.position)),ground_kind(ground(c,f,{s.position.x,s.plant_y})),s.position.y-s.plant_y};
        if(bad.pot!=bad.top&&std::none_of(places_.bad_pot_ground.begin(),places_.bad_pot_ground.end(),[&](const auto& old){return old.pot==bad.pot&&old.top==bad.top;}))places_.bad_pot_ground.push_back(std::move(bad));++state_.log["dead_spot"];break;
    }
    return error;
}
std::string AiPlantPlacement::place65(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    auto error=place6(c,f,key,point,facing);if(one_of(error,{"need pot","need lily","spike needs soil"})){++state_.log["skip:"+error];return "memo";}return error;
}
std::string AiPlantPlacement::place6(AiTacticalContext& c,const AiPlantPlacementFrame& f,const std::string& key,Point point,int facing){
    const auto& card=c.services.card(key);const auto& behavior=card.behavior;
    for(const auto& s:f.empty_supports)if(std::abs(ai_wrap_delta(s.position.x,point.x,c.frame.width))<c.frame.tile*.6&&std::abs(s.position.y-point.y)<c.frame.tile&&!one_of(behavior,{"pot","lily","spike"}))return try_deploy(c,f,key,{s.position.x,s.plant_y},{},facing);
    if(!one_of(behavior,{"pot","lily","gravebuster","coffee","flying56","ghost","vine"})){
        const auto* cell=ground(c,f,point);const bool water=cell&&cell->water,natural=cell&&one_of(cell->kind,{"土","草","沙","沙土","沙草","雪","空","水"});
        if(water&&!card.aquatic){if(has(f.deck,"plant:睡莲")&&c.ready("plant:睡莲"))return try_deploy(c,f,"plant:睡莲",point,{},facing);return "need lily";}
        if(!water&&!natural&&!has(f.secrets,"secret:无土栽培")){if(behavior=="spike")return "spike needs soil";if(has(f.deck,"plant:花盆")&&c.ready("plant:花盆"))return try_deploy(c,f,"plant:花盆",point,{},facing);return "need pot";}
    }
    return try_deploy(c,f,key,point,{},facing);
}
}
