from pathlib import Path
p=Path('cold72_export.cpp');t=p.read_text(encoding='utf8')
def sub(a,b):
    global t
    assert t.count(a)==1,a
    t=t.replace(a,b)
sub('#include "sim/pvp/hand/graphics.h"\n','''#include "sim/pvp/hand/graphics.h"
#include "sim/pvp/gen/pm_content_catalog.h"
#include "sim/pvp/gen/pm_expansion_catalog.h"
#include "sim/pvp/gen/pm_native_targets.h"
#include "sim/pvp/gen/pm_native_scale.h"
#include "sim/pvp/gen/pm_pvp56_plants_catalog.h"
''')
sub('        out["globals"]=globals;','''        const auto names=[&](const V& v){J list=J::array();for(const auto& item:py::iter_list(v).items())list.push_back(py_str(item));return list;};
        out["constants"]={{"content_plants",names(pm_content_catalog::PLANTS)},{"content_zombies",names(pm_content_catalog::ZOMBIES)},{"black_zombies",names(pm_expansion_catalog::BLACK_ZOMBIES)},
            {"black_bites",names(pm_native_targets::BLACK_BITE_VARIANTS)},{"air_plants",names(pm_pvp56_plants_catalog::AIR_PLANTS)},{"scale_factor",parsed(pm_native_scale::FACTOR)}};
        out["globals"]=globals;''')
p.write_text(t,encoding='utf8')
p=Path('match_probe.cpp');t=p.read_text(encoding='utf8')
sub('''        full_content=true;content_damage_enabled=true;full_bonus=true;installed=true;\n''','''        const auto& constants=cold.at("constants");
        custom_plants=constants.at("content_plants").get<std::vector<std::string>>();content_rules.custom_zombies=constants.at("content_zombies").get<std::vector<std::string>>();
        combat_rules.black_variants=constants.at("black_zombies").get<std::vector<std::string>>();combat_rules.black_hero_bite_variants=constants.at("black_bites").get<std::vector<std::string>>();
        collision.unit_scale=constants.at("scale_factor").get<decltype(collision.unit_scale)>();
        for(const auto& [name,sprite]:runtime.presentation.atlas)if(name.ends_with("-帧0"))collision.flyer_image_height[name.substr(0,name.size()-5)]=sprite.height;
        plant_rules.air_plants=constants.at("air_plants").get<std::vector<std::string>>();plant_rules.flying_plants=plant_rules.air_plants;std::erase(plant_rules.flying_plants,std::string("幽灵辣椒"));
        plant_rules.metal=g.at("金属").get<std::vector<std::string>>();plant_rules.bosses=g.at("boss").get<std::vector<std::string>>();plant_rules.thrown=rules.thrown;
        battle.wind_environment.zombie_speed_max=g.at("zbspeedmax");
        action_state.large_zombies.clear();for(const auto& [name,size]:g.at("大尸").items())action_state.large_zombies.push_back(name);
        navigation.ladder_count=g.at("梯子尸数");
        full_content=true;content_damage_enabled=true;full_bonus=true;installed=true;
''')
sub('''        public_sync.sync(tick_state.present,true);\n        for(const auto seat:tick_state.present){\n            const auto& player=''','''        garden.configure_locked_secrets();expansion.configure_locked_secrets();zsecrets.configure_locked();
        public_sync.sync(tick_state.present,true);\n        for(const auto seat:tick_state.present){\n            const auto& player=''')
# Duo/coop publish these per seat.
sub('''{"commands",nullptr},''','''{"commands",seat_commands()},''')
sub('''{"rally_points",nullptr}''','''{"rally_points",seat_rallies()}''')
sub('''    J players_json()const{\n''','''    J seat_commands()const{
        if(battle.mode!=MatchMode::duo&&battle.mode!=MatchMode::coop)return nullptr;
        J out=J::object();for(const auto seat:tick_state.present)if(team_of(seat)==Seat::zombie)out[seat_name(seat)]=commands.by_seat[seat_index(seat)]==PathMode::follow_hero?"follow":"attack";return out;
    }
    J seat_rallies()const{
        if(battle.mode!=MatchMode::duo&&battle.mode!=MatchMode::coop)return nullptr;
        J out=J::object();for(const auto seat:tick_state.present)if(team_of(seat)==Seat::zombie){const auto& flag=hero_flags.by_seat[seat_index(seat)];out[seat_name(seat)]=flag?J{{"x",flag->x},{"y",flag->y}}:J(nullptr);}return out;
    }
    J players_json()const{
''')
p.write_text(t,encoding='utf8')
# Registered through the real id sequence: register_unit assigns the id, not the probe.
p=Path('probes/content_phase_probe.cpp');t=p.read_bytes().decode('utf8')
a='''const auto id="tentacle:"+std::to_string(all_plants.size());plant->source.id.set(id);plant->source.owner.set("plant");'''
assert t.count(a)==1
t=t.replace(a,'''const auto id=tentacle_id(all_plants.size());plant->source.id.set(id);plant->source.owner.set("plant");''')
nl='\r\n' if '\r\n' in t else '\n'
a='    ContentCombatState combat_state;'+nl;assert t.count(a)==1
t=t.replace(a,a+'    virtual std::string tentacle_id(size_t n){return "tentacle:"+std::to_string(n);}'+nl)
p.write_bytes(t.encode('utf8'))
