#define PVZ72_FLYING_PLANTS_PROBE_EMBEDDED
#include "flying_plants_probe.cpp"
#include "sim/typed/scarecrow.h"

namespace {
struct ScarecrowProbe : FlyingPlantsProbe,ScarecrowServices {
    Scarecrows scarecrows{battle,sight,*this};
    J crow_calls=J::array(),crow_events=J::array();
    std::optional<std::string> child;
    bool observe_scarecrows=false;
    explicit ScarecrowProbe(int64_t seed,double width,double splash):FlyingPlantsProbe(seed,width,splash){}
    std::optional<std::string> spawn_echo_crow(Point point,double direction,const std::string& parent)override {
        crow_calls.push_back({"zombie:乌鸦","zombie",point.x,point.y,direction,true,{{"id",parent}},battle.spawn_ban_exempt});
        before("crow_spawn");after("crow_spawn");return child;
    }
    void crow_echo_event(const std::string& source,const Field<std::string>& scarecrow,const std::string& child)override {
        crow_events.push_back({"crow_echo",{{"source",source},
            {"scarecrow",scarecrow.present() && !scarecrow.is_null()?J(scarecrow.get()):J(nullptr)},{"entity",child}}});
        before("crow_event");after("crow_event");
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="scarecrow_setup") {
            observe_scarecrows=true;child.reset();if(!op.at("child").is_null())child=op.at("child").get<std::string>();
            battle.spawn_ban_exempt=op.value("exempt",0);
        }else if(name=="scarecrow_suspended") {
            battle.suspended_graves.clear();
            for(const auto& value:op.at("units"))battle.suspended_graves.push_back(units.at(value.get<size_t>()));
        }else if(name=="scarecrow_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());const auto& fields=op.at("fields");
            read(fields,"_pvp_base_speed",unit.base_speed);read(fields,"_pvp_walk_speed",unit.walk_speed);
            read(fields,"_pvp_hop_clock",unit.hop_clock);read(fields,"_pvp_flight",unit.flight);
            read(fields,"移速",unit.native.move_speed);read(fields,"_pvp_max_hp",unit.max_hp);
            if(fields.contains("_pvp_grave"))unit.protection.grave=fields.at("_pvp_grave").get<bool>();
        }else if(name=="scarecrow_configure")result=scarecrows.configure(units.at(op.at("unit").get<size_t>()),op.at("name").get<std::string>(),op.at("hp"));
        else if(name=="scarecrow_living") {
            result=J::array();for(const auto& unit:scarecrows.living())result.push_back(label(CombatTarget::zombie(unit)));
        }else if(name=="scarecrow_aura") {
            result=J::array();for(const auto& [row,column]:scarecrows.aura_cells())result.push_back({row,column});
        }else if(name=="scarecrow_slow")result=Scarecrows::slow_factor(plant_ref(op.at("plant").get<size_t>()),scarecrows.aura_cells());
        else if(name=="scarecrow_goal" || name=="scarecrow_step" || name=="crow_echo") {
            try {
                if(name=="scarecrow_goal") {
                    const auto goal=scarecrows.grave_goal(units.at(op.at("unit").get<size_t>()));
                    if(goal)result=label(CombatTarget::zombie(goal));
                }else if(name=="scarecrow_step")scarecrows.advance(units.at(op.at("unit").get<size_t>()),op.at("factor"));
                else {
                    const auto child=scarecrows.crow_echo({op.at("point").at(0),op.at("point").at(1)},op.at("id"));
                    if(child)result=*child;
                }
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return FlyingPlantsProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        FlyingPlantsProbe::extra_snapshot(row);if(!observe_scarecrows)return;
        J records=J::array();
        for(const auto& unit:units) {
            J fields=J::object();write(fields,"_pvp_base_speed",unit->base_speed);write(fields,"_pvp_walk_speed",unit->walk_speed);
            write(fields,"_pvp_hop_clock",unit->hop_clock);write(fields,"_pvp_flight",unit->flight);
            write(fields,"移速",unit->native.move_speed);write(fields,"_pvp_max_hp",unit->max_hp);
            write(fields,"_pvp_bite_plant",unit->patch.bite_plant);write(fields,"_pvp_no_attack",unit->patch.no_attack);
            write(fields,"_pvp_no_hero_attack",unit->source.no_hero_attack);write(fields,"_pvp_content",unit->source.content);
            records.push_back(fields);
        }
        row["scarecrows"]={{"units",records},{"calls",crow_calls},{"events",crow_events},{"exempt",battle.spawn_ban_exempt}};
    }
};
J run_scarecrows(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ScarecrowProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));
    probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;
    }
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: scarecrow72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("scarecrow fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_scarecrows(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
