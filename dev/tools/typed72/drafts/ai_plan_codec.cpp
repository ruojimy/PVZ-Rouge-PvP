#include "sim/typed/ai_plan_codec.h"
#include <cmath>
#include <limits>

namespace pvz::typed72 {
namespace {
bool truth(const WireObject& value){
    if(value.is_null())return false;if(value.is_boolean())return value.get<bool>();if(value.is_number())return value.get<double>()!=0.;
    if(value.is_string())return !value.get_ref<const std::string&>().empty();return !value.empty();
}
bool flag(const WireObject& j,const char* key,bool fallback){const auto it=j.find(key);return it==j.end()?fallback:truth(*it);}
}
AiPlan decode_ai_plan(const WireObject& raw,std::span<const std::string> deck){
    if(!raw.is_object())throw std::invalid_argument("plan must be an object");
    const auto priorities=raw.find("priority");if(priorities==raw.end()||!priorities->is_array())throw std::invalid_argument("priority list required");
    AiPlan plan;
    const auto in_deck=[&](const std::string& key){return std::find(deck.begin(),deck.end(),key)!=deck.end();};
    for(const auto& value:*priorities){
        if(!value.is_string())throw std::invalid_argument("priority contains a card outside your playable deck");
        const auto key=value.get<std::string>();
        if(!in_deck(key)||key.starts_with("secret:")||key.starts_with("zsecret:"))throw std::invalid_argument("priority contains a card outside your playable deck");
        if(std::find(plan.priority.begin(),plan.priority.end(),key)==plan.priority.end())plan.priority.push_back(key);
    }
    const auto stance=raw.value("stance",WireObject("hold"));
    if(stance=="hold")plan.stance=AiStance::hold;else if(stance=="advance")plan.stance=AiStance::advance;
    else if(stance=="hunt")plan.stance=AiStance::hunt;else if(stance=="kite")plan.stance=AiStance::kite;
    else if(stance=="retreat")plan.stance=AiStance::retreat;else throw std::invalid_argument("invalid stance");
    const auto quotas=raw.value("quotas",WireObject::object());if(!quotas.is_object())throw std::invalid_argument("invalid quota");
    for(const auto& [key,value]:quotas.items()){
        if(!in_deck(key)||!value.is_number_integer()||value.is_boolean()||(value.is_number_unsigned()&&value.get<uint64_t>()>700))throw std::invalid_argument("invalid quota");
        const auto amount=value.get<int64_t>();if(amount<0||amount>700)throw std::invalid_argument("invalid quota");plan.quotas.emplace_back(key,amount);
    }
    const auto number=[&](const char* key,double fallback){
        const auto it=raw.find(key);if(it==raw.end())return fallback;
        if(!it->is_number()||!std::isfinite(it->get<double>()))throw std::invalid_argument(std::string("invalid numeric field ")+key);return it->get<double>();
    };
    // Preserve validation order: target_x is tested before distance etc.
    plan.reserve=number("reserve",0.);if(raw.contains("target_x"))plan.target_x=number("target_x",0.);
    plan.distance=number("distance",350.);plan.deploy_ahead=number("deploy_ahead",120.);plan.economy_offset=number("economy_offset",100.);
    plan.jump_every=number("jump_every",0.);plan.teleport_hp=number("teleport_hp",0.);
    if(const auto saved=raw.find("save_for");saved!=raw.end()&&truth(*saved)){
        if(!saved->is_string()||std::find(plan.priority.begin(),plan.priority.end(),saved->get<std::string>())==plan.priority.end())throw std::invalid_argument("save_for must be a priority card");
        plan.save_for=saved->get<std::string>();
    }
    plan.evade=flag(raw,"evade",false);plan.jump_on_block=flag(raw,"jump_on_block",true);plan.dodge_jump=flag(raw,"dodge_jump",true);plan.mark=flag(raw,"mark",true);
    const auto command=raw.value("command",WireObject("attack"));
    if(command=="follow")plan.command=PathMode::follow_hero;else if(command=="attack")plan.command=PathMode::attack_plants;else plan.command.reset();
    return plan;
}
} // namespace pvz::typed72
