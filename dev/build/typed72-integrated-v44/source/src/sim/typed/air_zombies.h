#pragma once
#include "sim/typed/zombie_fields.h"
#include <string_view>
namespace pvz::typed72 {
inline bool air_zombie_name(std::string_view id){
    return id=="海盗鹦鹉"||id=="乌鸦"||id=="气球僵尸"||id=="飞贼僵尸"||id=="克苏鲁之仆";
}
inline bool air_zombie_card(std::string_view id){
    return id.starts_with("zombie:")&&air_zombie_name(id.substr(7));
}
inline bool retract_bungee(std::string_view name,ZombieNativeState& native,const Motion& p){
    if(name!="飞贼僵尸")return false;
    if(!native.leaving.present()){
        native.leaving.set(0.);native.entry.set(0.);native.entry_end=native.entry_start;native.entry_start.set({p.x,p.y});
    }
    return true;
}
}
