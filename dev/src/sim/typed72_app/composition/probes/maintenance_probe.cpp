#define PVZ72_RESOURCES_PROBE_EMBEDDED
#include "resources_probe.cpp"
#include "sim/typed/grave_clock.h"
#include "sim/typed/plant_maintenance.h"

namespace {
struct MaintenanceProbe : ResourcesProbe {
    GraveIdleRules grave_rules{20.,20.,.5,6.,"稻草人"};
    GraveClock grave_clock{battle,economy_state,grave_rules};
    PlantDeathRules death_rules;
    PlantDeathState death_state;
    PlantDeathPolicy death_policy{battle,resources,economy_state,death_state,death_rules};
    PlantMaintenance maintenance{battle,world_region,*this,*this,static_cast<ZombieMotionServices&>(*this),death_policy};
    bool observe_graves=false,observe_deaths=false;
    explicit MaintenanceProbe(int64_t seed,double width,double splash):ResourcesProbe(seed,width,splash){}

    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="grave_clock_setup") {
            observe_graves=true;
            present.clear();
            for(const auto& seat:op.at("present"))present.push_back(parse_seat(seat.get<std::string>()));
        }else if(name=="grave_clock_state") {
            if(op.contains("deathmatch"))battle.protection.deathmatch=op.at("deathmatch");
            if(op.contains("last_stand")) {
                world.last_stand_order.clear();
                for(auto& until:world.last_stand)until.reset();
                for(const auto& [seat,time]:op.at("last_stand").items()) {
                    const auto side=parse_seat(seat);
                    world.last_stand[seat_index(side)]=time.get<double>();
                    world.last_stand_order.push_back(side);
                }
            }
        }else if(name=="grave_idle_fields") {
            auto& unit=*units.at(op.at("unit").get<size_t>());
            const auto& fields=op.at("fields");
            read(fields,"_pvp_producer",unit.producer);
            read(fields,"_pvp_idle",unit.idle);
            read(fields,"_pvp_zs_awake",unit.permanently_awake);
            read(fields,"_pvp_production_rate",unit.production_rate);
            read(fields,"冰冻",unit.body.ice);
            read(fields,"黄油",unit.body.butter);
            read(fields,"眩晕",unit.body.stun);
            read(fields,"灰烬",unit.body.ash);
            read(fields,"_pvp_owner",unit.source.owner);
            read(fields,"_pvp_id",unit.source.id);
            read(fields,"_pvp_content",unit.source.content);
            read(fields,"魅惑",unit.source.charmed);
            if(fields.contains("位置"))unit.body.motion=motion(fields.at("位置"));
            if(fields.contains("血量"))unit.body.hp=fields.at("血量");
            if(fields.contains("_pvp_grave"))unit.protection.grave=fields.at("_pvp_grave");
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="灰烬")unit.body.ash.erase();
                else if(key=="魅惑")unit.source.charmed.erase();
                else if(key=="_pvp_owner")unit.source.owner.erase();
                else if(key=="_pvp_id")unit.source.id.erase();
                else throw std::invalid_argument("grave erase field");
            }
        }else if(name=="grave_clock_step") {
            std::vector<ZombieRef> selected;
            for(const auto& index:op.at("graves"))selected.push_back(units.at(index.get<size_t>()));
            grave_clock.advance(selected,present,op.at("multiplier"));
        }else if(name=="grave_idle_step") {
            result=grave_clock.idle(units.at(op.at("unit").get<size_t>()),op.at("factor"),present);
        }else if(name=="grave_wake") {
            grave_clock.wake(units.at(op.at("unit").get<size_t>()),op.at("cause"));
        }else if(name=="grave_wake_input") {
            const auto& id=op.at("id");
            const auto answer=grave_clock.wake_input(parse_seat(op.at("side").get<std::string>()),
                id.is_string()?std::optional<std::string>(id.get<std::string>()):std::nullopt);
            static constexpr const char* messages[]={"","只有僵尸方可唤醒墓碑","墓碑编号无效","墓碑不存在","墓碑不需要照料"};
            result=messages[size_t(answer)];
        }else if(name=="death_policy_setup") {
            observe_deaths=true;
            death_rules.zombie_secrets_enabled=op.at("enabled");
            death_rules.nuclear_secret=op.at("nuclear");
            death_rules.brain_holders.clear();death_rules.conversion_holders.clear();
            for(const auto& seat:op.at("brain_holders"))death_rules.brain_holders.push_back(parse_seat(seat.get<std::string>()));
            for(const auto& seat:op.at("conversion_holders"))death_rules.conversion_holders.push_back(parse_seat(seat.get<std::string>()));
            death_rules.conversion_forms=op.at("forms").get<decltype(death_rules.conversion_forms)>();
        }else if(name=="death_plant_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());const auto& fields=op.at("fields");
            read(fields,"_pvp_zs_killed",plant.secret_killed);
            read(fields,"_pvp_temporary",plant.temporary);
            read(fields,"_pvp_transform_succeeded",plant.transform_succeeded);
            read(fields,"睡觉",plant.sleep);read(fields,"埋藏",plant.buried);
            read_death(fields,"黑白",plant.monochrome);
            if(fields.contains("方向"))plant.facing=fields.at("方向");
            read_death(fields,"死",plant.dead);read_death(fields,"铲死",plant.shovel_dead);
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="睡觉")plant.sleep.erase();
                else if(key=="死")plant.dead.erase();
                else if(key=="铲死")plant.shovel_dead.erase();
                else throw std::invalid_argument("plant erase field");
            }
        }else if(name=="plant_killed")death_policy.killed(plant_ref(op.at("plant").get<size_t>()));
        else if(name=="death_supplement")result=death_policy.supplement(op.at("index").get<size_t>());
        else if(name=="death_doom")result=death_policy.second_doom_ash(op.at("index"));
        else if(name=="maintenance_run") {
            try{maintenance.run();}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }
        else return ResourcesProbe::extra_operation(op,result);
        return true;
    }

    void extra_snapshot(J& row)override {
        ResourcesProbe::extra_snapshot(row);
        if(observe_graves) {
            J values=J::array();
            for(const auto& unit:units) {
                J fields=J::object();
                write(fields,"_pvp_producer",unit->producer);write(fields,"_pvp_idle",unit->idle);
                write(fields,"_pvp_zs_awake",unit->permanently_awake);write(fields,"_pvp_production_rate",unit->production_rate);
                values.push_back({fields,grave_clock.level(*unit),grave_clock.drowsy(*unit)});
            }
            row["grave_idle"]={{"units",values},{"progress",economy_state.grave_progress}};
        }
        if(observe_deaths) {
            J conversions=J::array(),points=J::array(),suns=J::array();
            for(const auto& item:death_state.conversions)conversions.push_back({item.name,item.position.x,item.position.y,item.facing,seat_name(item.seat)});
            for(const auto point:economy_state.death_points)points.push_back({point.x,point.y});
            for(const auto& sun:world_region.loose_suns)suns.push_back(sun_json(*sun));
            row["plant_deaths"]={{"conversions",conversions},{"points",points},{"suns",suns}};
        }
    }
};
J run_maintenance(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    MaintenanceProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);
    probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));
        probe.battle.protection.secrets.enabled=true;
    }
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: maintenance72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("maintenance fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_maintenance(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
