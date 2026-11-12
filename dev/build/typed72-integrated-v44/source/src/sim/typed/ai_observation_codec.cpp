#include "sim/typed/ai_observation_codec.h"
namespace pvz::typed72 {
namespace {
using J=WireObject;
template<class T>J nullable(const std::optional<T>& value){return value?J(*value):J(nullptr);}
template<class T,class F>J list(const T& values,F f){J out=J::array();for(const auto& value:values)out.push_back(f(value));return out;}
J target(const AiObservedTarget& v){return {{"x",v.position.x},{"y",v.position.y},{"dx",v.dx},{"dy",v.dy},{"plant_y",v.plant_y},{"zone",v.zone},{"card_id",v.card},{"producer",v.producer}};}
J tool(const AiObservedTool& v){return {{"id",v.id},{"card_id",v.card},{"name",nullable(v.name)},{"dx",v.dx},{"dy",v.dy},{"zone",v.zone},{"hp_pct",v.hp_pct}};}
}
WireObject encode_ai_observation(const AiObservation& v){
    const auto& h=v.hero;const auto& e=v.enemy_hero;
    return {{"schema","pvp-ai-obs-1"},{"match_id",v.match_id},{"observation_id",v.observation_id},{"tick",v.tick},{"time",v.time},{"side",v.side==Seat::plant?"plant":"zombie"},{"night",v.night},{"world_width",v.width},
        {"producer_count",v.producer_count},{"sleeping_plants",list(v.sleeping_plants,target)},{"empty_supports",list(v.empty_supports,target)},{"deathmatch",v.deathmatch},{"strategy_plan_id",v.plan_id},
        {"hero",{{"hp_pct",h.hp_pct},{"x",h.x},{"y",h.y},{"vx",h.vx},{"vy",h.vy},{"zone",h.zone},{"facing",h.facing},{"grounded",h.grounded},{"jumps_left",h.jumps_left},{"frozen",h.frozen},{"slowed",h.slowed},{"buttered",h.buttered},{"poison_level",h.poison_level},{"teleport_ready_in",h.teleport_ready_in}}},
        {"enemy_hero",{{"hp_pct",e.hp_pct},{"dx",e.dx},{"dy",e.dy},{"zone",e.zone},{"facing",e.facing},{"resource",e.resource}}},{"resource",v.resource},{"income_per_second",v.income},
        {"cards",list(v.cards,[](const auto& c)->J{return {{"id",c.id},{"name",c.name},{"cost",c.cost},{"cooldown_left",c.cooldown_left},{"affordable",c.affordable},{"ready",c.ready},{"behavior",c.behavior},{"producer",c.producer},{"mushroom",c.mushroom},{"range",nullable(c.range)}};})},
        {"threats",list(v.threats,[](const auto& t)->J{return {{"type",t.type},{"direction",t.from_left?"left":"right"},{"eta_ms",t.eta_ms},{"severity",t.severity},{"splash",t.splash},{"source",t.projectile?"projectile":"melee"}};})},{"danger",v.danger},
        {"zones",list(v.zones,[](const auto& z)->J{return {{"zone",z.zone},{"friendly_value",z.friendly_value},{"enemy_value",z.enemy_value},{"pressure",z.pressure}};})},
        {"enemy_units",list(v.enemy_units,[](const auto& u)->J{return {{"card_id",u.card},{"name",nullable(u.name)},{"dx",u.dx},{"dy",u.dy},{"zone",u.zone},{"hp_pct",u.hp_pct},{"mobile",u.mobile},{"behavior",nullable(u.behavior)}};})},
        {"deploy_anchors",list(v.deploy_anchors,[](const auto& a)->J{return {{"id",a.id},{"zone",a.zone},{"x",a.x},{"hp_pct",a.hp_pct}};})},
        {"collectable",list(v.collectable,[](const auto& c)->J{return {{"id",c.id},{"dx",c.dx},{"amount",c.amount},{"source",nullable(c.source)}};})},
        {"tools",v.side==Seat::plant?J{{"cannons",list(v.cannons,tool)},{"cannon_aimed",v.cannon_aimed},{"shovel_targets",list(v.shovel_targets,tool)}}:J::object()},
        {"my_unit_count",v.my_unit_count},{"enemy_unit_count",v.enemy_unit_count}};
}
} // namespace pvz::typed72
