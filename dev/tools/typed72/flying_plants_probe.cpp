#define PVZ72_PLANT_REGION_PROBE_EMBEDDED
#include "plant_region_probe.cpp"
#include "sim/typed/flying_plants.h"
#include "sim/typed/sweet_taunts.h"

namespace {
struct FlyingPlantsProbe : PlantRegionProbe,ContentUnitDamage,FlyingPlantServices {
    SeatCommands commands;
    SeatPathTracking path_banks{battle,navigation,path_rules,sight,hero_flags,commands};
    SweetTaunts taunts{battle,navigation,path_banks,path_rules,false};
    ContentTargets target_dispatch;
    ContentQueries queries;
    FlyingPlants flying;
    EntityRoster flight_records;
    J flying_events=J::array(),flying_draws=J::array();
    bool observe_flying=false,gate_flying=false;
    explicit FlyingPlantsProbe(int64_t seed,double width,double splash)
        :PlantRegionProbe(seed,width,splash),target_dispatch(battle,static_cast<ContentUnitDamage&>(*this),collision,width),
         queries(battle,target_dispatch,taunts),flying(battle,queries,target_dispatch,sight,collision,*this){}
    void ordinary(size_t index,double facing,double amount)override {
        before("content_damage");PlantRegionProbe::ordinary(index,facing,amount);after("content_damage");
    }
    void surface(size_t index,double facing,double amount)override {
        before("content_damage");PlantRegionProbe::surface(index,facing,amount);after("content_damage");
    }
    void flying_sweep(const FlyingSweepEvent& event)override {
        flying_events.push_back({"asparagus_sweep",{{"source",event.source.present() && !event.source.is_null()?J(event.source.get()):J(nullptr)},
            {"angle",event.angle},{"facing",event.facing}}});
        before("flying_event");after("flying_event");
    }
    void draw_flying_shot(const EntityRef& entity)override {
        flying_draws.push_back({entity->source.id.get(),as_json(entity->motion.get())});
        before("flying_draw");after("flying_draw");
    }
    void plant_gate(size_t index)override {
        PlantRegionProbe::plant_gate(index);
        if(gate_flying)flying.advance(battle.plant_roster->at(index));
    }
    J content_label(const ContentTarget& target)const {
        if(const auto* plant=std::get_if<PlantRef>(&target)) {
            const auto found=std::find(all_plants.begin(),all_plants.end(),*plant);
            if(found==all_plants.end())throw std::logic_error("unregistered fixture plant");
            return J{{"plant",size_t(found-all_plants.begin())}};
        }
        return label(std::get<CombatTarget>(target));
    }
    static void read_plant_fields(CombatPlant& plant,const J& fields) {
        read(fields,"_pvp_content_age",plant.content_age);read(fields,"_pvp_one_shot",plant.one_shot);
        read(fields,"_pvp_aura_factor",plant.aura_factor);
        auto& state=plant.flying;
        read(fields,"_pvp_flying_clock",state.clock);read(fields,"_pvp_flying_rest",state.rest);
        read(fields,"_pvp_flying_mode",state.mode);read(fields,"_pvp_sweep_age",state.sweep_age);
        read(fields,"_pvp_sweep_angle",state.sweep_angle);read(fields,"_pvp_sweep_facing",state.sweep_facing);
        read(fields,"_pvp_last_fired",plant.last_fired);read(fields,"_pvp_flying_shots",state.shots);
    }
    static void read_shot_fields(Entity& entity,const J& fields) {
        if(fields.contains("位置"))entity.motion=motion(fields.at("位置"));
        if(fields.contains("方向"))entity.facing=fields.at("方向");
        read(fields,"_pvp_distance",entity.flying.distance);read(fields,"_pvp_owner",entity.source.owner);
        read(fields,"_pvp_flight_distance",entity.flight.distance);
        read(fields,"_pvp_hits",entity.flying.hits);read(fields,"_pvp_damage",entity.flying.damage);
        read(fields,"_pvp_piercing",entity.flying.piercing);read(fields,"_pvp_angle",entity.flying.angle);
        read(fields,"_pvp_content",entity.source.content);read(fields,"_pvp_flying56",entity.flying_plant);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="flying_setup") {observe_flying=true;battle.world_height.set(op.at("height"));}
        else if(name=="flying_configure")result=flying.configure(plant_ref(op.at("plant").get<size_t>()),op.at("name").get<std::string>());
        else if(name=="flying_fields")read_plant_fields(*plant_ref(op.at("plant").get<size_t>()),op.at("fields"));
        else if(name=="flying_shot_fields")read_shot_fields(*flight_records.at(op.at("shot").get<size_t>()),op.at("fields"));
        else if(name=="flying_published")sight.solid=op.at("solid").get<decltype(sight.solid)>();
        else if(name=="flying_roster") {
            auto roster=std::make_shared<EntityRoster>();
            for(const auto& index:op.at("shots"))roster->push_back(flight_records.at(index.get<size_t>()));
            battle.runtime.entities.replace(std::move(roster));
        }else if(name=="flying_clear")result=flying.clear_line({op.at("start").at(0),op.at("start").at(1)},
            {op.at("end").at(0),op.at("end").at(1)});
        else if(name=="flying_wall")result=flying.wall_contact({op.at("start").at(0),op.at("start").at(1)},
            {op.at("delta").at(0),op.at("delta").at(1)});
        else if(name=="flying_nearby") {
            result=J::array();for(const auto& target:flying.nearby(plant_ref(op.at("plant").get<size_t>()),op.at("radius")))result.push_back(content_label(target));
        }else if(name=="flying_target") {
            const auto target=flying.turnip_target(plant_ref(op.at("plant").get<size_t>()));
            if(target)result=content_label(*target);
        }else if(name=="flying_reach") {
            const auto target=content_target(op.at("target"));result=flying.contact_reach(target,target_dispatch.point(target));
        }else if(name=="flying_before")flying.before_tick();
        else if(name=="flying_wind")wind.wind(units.at(op.at("unit").get<size_t>()),op.at("strength"));
        else if(name=="flying_tick" || name=="flying_fire" || name=="flying_projectiles" || name=="flying_region") {
            gate_flying=name=="flying_region";
            try {
                const auto plant=op.contains("plant")?plant_ref(op.at("plant").get<size_t>()):PlantRef{};
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,plant?source_ref(plant):nullptr,{}});
                NativeBirthScope births_scope(battle.runtime,static_cast<PlantRegionServices&>(*this));
                if(name=="flying_tick")flying.advance(plant);
                else if(name=="flying_fire")flying.fire(plant,op.at("angle"));
                else if(name=="flying_projectiles")flying.projectiles();
                else plants.run();
            }catch(const std::exception&) {
                gate_flying=false;if(!op.value("catch",false))throw;result={{"caught",true}};
            }
            gate_flying=false;
        }else return PlantRegionProbe::extra_operation(op,result);
        return true;
    }
    static void plant_fields(J& record,const CombatPlant& plant) {
        write(record,"_pvp_content_age",plant.content_age);write(record,"_pvp_one_shot",plant.one_shot);
        write(record,"_pvp_aura_factor",plant.aura_factor);
        const auto& state=plant.flying;
        write(record,"_pvp_flying_clock",state.clock);write(record,"_pvp_flying_rest",state.rest);
        write(record,"_pvp_flying_mode",state.mode);write(record,"_pvp_sweep_age",state.sweep_age);
        write(record,"_pvp_sweep_angle",state.sweep_angle);write(record,"_pvp_sweep_facing",state.sweep_facing);
        write(record,"_pvp_last_fired",plant.last_fired);write(record,"_pvp_flying_shots",state.shots);
    }
    static void shot_fields(J& record,const Entity& entity) {
        write(record,"_pvp_flying56",entity.flying_plant);write(record,"_pvp_distance",entity.flying.distance);
        write(record,"_pvp_hits",entity.flying.hits);write(record,"_pvp_angle",entity.flying.angle);
        write(record,"_pvp_damage",entity.flying.damage);write(record,"_pvp_piercing",entity.flying.piercing);
    }
    void extra_snapshot(J& row)override {
        PlantRegionProbe::extra_snapshot(row);if(!observe_flying)return;
        const auto remember=[&](const auto& roster){for(const auto& entity:roster)
            if(entity->flying.hits.present() && std::find(flight_records.begin(),flight_records.end(),entity)==flight_records.end())flight_records.push_back(entity);};
        const auto live=battle.runtime.entities.list();
        remember(*live);remember(battle.content_projectiles.flying);
        J hidden=J::array(),records=J::array();
        for(const auto& entity:battle.content_projectiles.flying){auto record=pea_state(entity);shot_fields(record,*entity);hidden.push_back(record);}
        for(const auto& entity:flight_records){auto record=pea_state(entity);shot_fields(record,*entity);records.push_back(record);}
        row["flying"]={{"events",flying_events},{"draws",flying_draws},{"hidden",hidden},{"records",records}};
        for(size_t i=0;i<live->size();++i)shot_fields(row["entities"][i],*live->at(i));
        for(size_t i=0;i<births.size();++i)shot_fields(row["effect_births"][i],*births[i]);
        for(size_t i=0;i<all_plants.size();++i)plant_fields(row["all_plants"][i],*all_plants[i]);
        for(size_t i=0;i<battle.plant_roster->size();++i)plant_fields(row["plants"][i],*battle.plant_roster->at(i));
    }
};
J run_flying_plants(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    FlyingPlantsProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
#ifndef PVZ72_FLYING_PLANTS_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: flying_plants72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("flying plant fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_flying_plants(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
