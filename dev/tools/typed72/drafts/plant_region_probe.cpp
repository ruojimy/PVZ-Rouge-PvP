#define PVZ72_RESOURCES_PROBE_EMBEDDED
#include "resources_probe.cpp"
#include "sim/typed/plant_region.h"
#include "sim/typed/plant_queries.h"

namespace {
struct PlantRegionProbe : ResourcesProbe,PlantRegionServices {
    PlantRegionRules plant_rules;
    PlantRegionState plant_environment;
    PlantRegion plants{battle,world_region,indexes,action_state,plant_environment,plant_rules,*this,*this};
    bool observe_plants=false;
    explicit PlantRegionProbe(int64_t seed,double width,double splash):ResourcesProbe(seed,width,splash){}
    void add_entity(std::string name,double facing,Motion point)override{ResourcesProbe::add_entity(std::move(name),facing,point);}
    void ordinary(size_t index,double facing,double amount)override{ResourcesProbe::ordinary(index,facing,amount);}
    void surface(size_t index,double facing,double amount)override{ResourcesProbe::surface(index,facing,amount);}
    void summon_zombie(std::string name,Motion point,double facing)override{ResourcesProbe::summon_zombie(std::move(name),point,facing);}
    void plant_gate(size_t index)override {
        render_log.push_back(J::array({"plant",index}));before("plant_gate");after("plant_gate");
    }
    bool star_target()override{return plant_star_target(battle,chart,size_t(world.source_index.value()));}
    std::span<const int64_t> pitcher_columns()override{return plant_pitcher_columns(*battle.plant_roster->at(size_t(world.source_index.value())));}
    bool edible(size_t index)override{return plant_edible_target(battle,index);}
    bool wind_target(size_t index)override{return plant_wind_target(*battle.runtime.entities.list()->at(index),rules.damaging);}
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="plant_region_setup") {
            observe_plants=true;
            plant_rules.air_plants=op.at("air").get<std::vector<std::string>>();
            plant_rules.flying_plants=op.at("flying").get<std::vector<std::string>>();
            plant_rules.metal=op.at("metal").get<std::vector<std::string>>();
            plant_rules.bosses=op.at("bosses").get<std::vector<std::string>>();
            plant_rules.thrown=rules.thrown;plant_rules.lantern_secret=op.value("lantern",false);
            plant_environment.pointer=cell(op.at("pointer"));plant_environment.held_card=op.at("held");
            plant_environment.wave=op.at("wave");plant_environment.placement_status=op.at("placement");
            plant_environment.selected_cannon.reset();
            if(!op.at("selected").is_null())plant_environment.selected_cannon=cell(op.at("selected"));
            const auto nearest=op.value("nearest",-1);indexes.nearest=nearest<0?std::nullopt:std::optional<size_t>(nearest);
            battle.runtime.freeze_flash.set(op.value("freeze",0.));
            world_region.water_offset=op.value("water_offset",0.);
            *battle.wind_environment.rain=std::vector<std::shared_ptr<std::vector<double>>>{};
            for(const auto& item:op.at("rain"))battle.wind_environment.rain->push_back(std::make_shared<std::vector<double>>(item.get<std::vector<double>>()));
            battle.wind_environment.zombie_speed_max=op.at("speed");
        }else if(name=="plant_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());const auto& fields=op.at("fields");
#define READ(n,k) read(fields,k,plant.n);
            PVZ72_PLANT_NUMBERS(READ)
#undef READ
            read(fields,"植物血",plant.hp);read(fields,"植物血上限",plant.max_hp);read(fields,"受伤",plant.hurt);
            read(fields,"模仿",plant.imitation);read(fields,"_pvp_copy_card",plant.copy_card);
            read(fields,"_pvp_owner",plant.source.owner);read(fields,"_pvp_content",plant.source.content);
            read(fields,"_pvp_variant",plant.source.variant);read(fields,"魅惑",plant.source.charmed);
            read_death(fields,"死",plant.dead);read_death(fields,"黑白",plant.monochrome);
            if(fields.contains("方向"))plant.facing=fields.at("方向");
            if(fields.contains("坐标"))plant.cell=cell(fields.at("坐标"));
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
#define ERASE(n,k) if(key==k){plant.n.erase();continue;}
                PVZ72_PLANT_NUMBERS(ERASE)
#undef ERASE
                if(key=="死")plant.dead.erase();else if(key=="魅惑")plant.source.charmed.erase();
                else throw std::invalid_argument("plant region erase");
            }
        }else if(name=="plant_unit") {
            auto& unit=*units.at(op.at("unit").get<size_t>());const auto& fields=op.at("fields");
            motion_unit(unit,fields);if(fields.contains("防具血量"))unit.body.armor_hp=fields.at("防具血量");
            read(fields,"_pvp_anchor_until",unit.protection.anchor_until);
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="魅惑")unit.source.charmed.erase();else if(key=="离开")unit.native.leaving.erase();
                else throw std::invalid_argument("plant target erase");
            }
        }else if(name=="plant_entity")read(op.at("fields"),"_pvp_flying56",births.at(op.at("entity").get<size_t>())->flying_plant);
        else if(name=="plant_query") {
            const auto query=op.at("query").get<std::string>();const auto index=op.at("index").get<size_t>();
            if(query=="star" || query=="support")world.source_index=int64_t(index);
            if(query=="support")result=plant_needs_support(battle,index,plant_rules.air_plants,plant_rules.flying_plants);
            else if(query=="star")result=plant_star_target(battle,chart,index);
            else if(query=="edible")result=edible(index);
            else if(query=="wind")result=wind_target(index);
            else throw std::invalid_argument("plant query");
        }else if(name=="plant_wind") {
            if(op.at("after").get<bool>())wind.after_plants();else wind.before_plants();
        }else if(name=="plant_region_run") {
            try {
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
                plants.run();
            }catch(const std::exception& error){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return ResourcesProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        ResourcesProbe::extra_snapshot(row);if(!observe_plants)return;
        J coins=J::array(),rain=J::array(),units_json=J::array();
        for(const auto& coin:action_state.coins)coins.push_back({coin.age,as_json(coin.motion),coin.cooldown,coin.kind});
        for(const auto& item:*battle.wind_environment.rain)rain.push_back(*item);
        for(const auto& unit:units) {
            J fields=J::object();write(fields,"出土",unit->native.emerged);write(fields,"离开",unit->native.leaving);
            write(fields,"出场",unit->native.entry);write(fields,"大小",unit->body.size);
            write(fields,"冰冻",unit->body.ice);write(fields,"黄油",unit->body.butter);write(fields,"眩晕",unit->body.stun);
            write_point(fields,"出场初位置",unit->native.entry_start);write_point(fields,"出场末位置",unit->native.entry_end);
            units_json.push_back(std::move(fields));
        }
        J suns=J::array();for(const auto& sun:world_region.loose_suns)suns.push_back(sun_json(*sun));
        row["plant_region"]={{"coins",coins},{"rain",rain},{"units",units_json},{"suns",suns},
            {"freeze",battle.runtime.freeze_flash.get()},{"placement",plant_environment.placement_status}};
        for(size_t i=0;i<births.size();++i)write(row["effect_births"][i],"_pvp_flying56",births[i]->flying_plant);
        const auto entities=battle.runtime.entities.list();
        for(size_t i=0;i<entities->size();++i)write(row["entities"][i],"_pvp_flying56",entities->at(i)->flying_plant);
    }
};
J run_plant_region(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    PlantRegionProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);
    probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()) {
        probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;
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
        if(argc!=3)throw std::invalid_argument("usage: plant_region72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("plant fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_plant_region(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
