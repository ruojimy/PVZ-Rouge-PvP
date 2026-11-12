#define PVZ72_FLYING_PLANTS_PROBE_EMBEDDED
#include "flying_plants_probe.cpp"
#include "sim/typed/mortar_plants.h"

namespace {
struct MortarPlantsProbe : FlyingPlantsProbe,MortarPlantServices {
    MortarPlants mortars{battle,queries,target_dispatch,*this};
    J mortar_events=J::array();
    bool observe_mortars=false,gate_mortars=false;
    explicit MortarPlantsProbe(int64_t seed,double width,double splash):FlyingPlantsProbe(seed,width,splash){}
    void mortar_event(const MortarPlantEvent& event)override {
        J fields={{"source",event.source.present() && !event.source.is_null()?J(event.source.get()):J(nullptr)},
                  {"targets",event.targets}};
        if(!event.spring)fields["shots"]=event.shots;
        mortar_events.push_back({event.spring?"spring_whip":"mortar_volley",fields});
        ;;
    }
    void spring_knockback(size_t index,double amount)override{knockback(index,amount);}
    void plant_gate(size_t index)override {
        FlyingPlantsProbe::plant_gate(index);
        if(gate_mortars)mortars.advance(battle.plant_roster->at(index));
    }
    static void mortar_fields(Entity& entity,const J& fields) {
        read_shot_fields(entity,fields);auto& state=entity.mortar;
        read(fields,"_pvp_mortar",state.mortar);read(fields,"_pvp_mortar_bonus_done",state.bonus_done);
        read(fields,"_pvp_mortar_speed",state.speed);read(fields,"_pvp_mortar_target",state.target);
        read(fields,"_pvp_multi_red",state.multi_red);read(fields,"三向蓝火弹",state.tripea_blue);
        read(fields,"_pvp_umbrella_reflected",state.umbrella_reflected);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="mortar_setup") {
            observe_mortars=true;auto secrets=std::make_shared<std::vector<std::string>>();
            if(op.at("blue").get<bool>())secrets->push_back("三向蓝火");
            world.globals.secrets.set(std::move(secrets));
        }
        else if(name=="mortar_configure")result=mortars.configure(plant_ref(op.at("plant").get<size_t>()),op.at("name").get<std::string>());
        else if(name=="mortar_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());const auto& fields=op.at("fields");
            read_plant_fields(plant,fields);read(fields,"_pvp_attack_clock",plant.attack_clock);
        }else if(name=="mortar_shot_fields")mortar_fields(*births.at(op.at("entity").get<size_t>()),op.at("fields"));
        else if(name=="mortar_muzzle") {
            const auto [point,direction]=mortars.muzzle(plant_ref(op.at("plant").get<size_t>()));
            result={{point.x,point.y},direction};
        }else if(name=="mortar_targets") {
            result=J::array();for(const auto& target:mortars.mortar_targets(plant_ref(op.at("plant").get<size_t>())))result.push_back(content_label(target));
        }else if(name=="mortar_lead") {
            const auto point=mortars.lead(content_target(op.at("target")));result={point.x,point.y};
        }else if(name=="mortar_aim") {
            const auto aim=mortars.aim(plant_ref(op.at("plant").get<size_t>()),content_target(op.at("target")));
            J solution=nullptr;if(aim.solution)solution={aim.solution->time,aim.solution->vx,aim.solution->vy};
            result={{aim.start.x,aim.start.y},solution};
        }else if(name=="mortar_damage") {
            try{result=MortarPlants::projectile_damage(births.at(op.at("entity").get<size_t>()),content_target(op.at("target")),op.at("amount"));}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="mortar_red")MortarPlants::red_pea(births.at(op.at("entity").get<size_t>()));
        else if(name=="mortar_split")mortars.split_pea_blue(births.at(op.at("entity").get<size_t>()));
        else if(name=="mortar_before")mortars.before_entities();
        else if(name=="mortar_tick" || name=="mortar_fire" || name=="spring_fire" || name=="mortar_region") {
            gate_mortars=name=="mortar_region";
            try {
                const auto plant=op.contains("plant")?plant_ref(op.at("plant").get<size_t>()):PlantRef{};
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,plant?source_ref(plant):nullptr,{}});
                NativeBirthScope births_scope(battle.runtime,static_cast<PlantRegionServices&>(*this));
                if(name=="mortar_tick")mortars.advance(plant);
                else if(name=="mortar_fire")result=mortars.mortar(plant);
                else if(name=="spring_fire")result=mortars.spring(plant);
                else plants.run();
            }catch(const std::exception&) {
                gate_mortars=false;if(!op.value("catch",false))throw;result={{"caught",true}};
            }
            gate_mortars=false;
        }else return FlyingPlantsProbe::extra_operation(op,result);
        return true;
    }
    static void mortar_snapshot(J& row,const Entity& entity) {
        const auto& state=entity.mortar;
        write(row,"_pvp_mortar",state.mortar);write(row,"_pvp_mortar_bonus_done",state.bonus_done);
        write(row,"_pvp_mortar_speed",state.speed);write(row,"_pvp_mortar_target",state.target);
        write(row,"_pvp_multi_red",state.multi_red);write(row,"三向蓝火弹",state.tripea_blue);
        write(row,"_pvp_umbrella_reflected",state.umbrella_reflected);
    }
    void extra_snapshot(J& row)override {
        FlyingPlantsProbe::extra_snapshot(row);if(!observe_mortars)return;
        J swipes=J::array();for(const auto& swipe:mortars.swipes)swipes.push_back({swipe.tick,swipe.point.x,swipe.point.y,swipe.angle});
        J blown=J::array();for(const auto& unit:units){J fields=J::object();write(fields,"_pvp_blown",unit->body.blown);blown.push_back(fields);}
        row["mortars"]={{"events",mortar_events},{"swipes",swipes},{"units",blown}};
        for(size_t i=0;i<all_plants.size();++i)write(row["all_plants"][i],"_pvp_attack_clock",all_plants[i]->attack_clock);
        for(size_t i=0;i<battle.plant_roster->size();++i)write(row["plants"][i],"_pvp_attack_clock",battle.plant_roster->at(i)->attack_clock);
        for(size_t i=0;i<battle.runtime.entities.list()->size();++i)mortar_snapshot(row["entities"][i],*battle.runtime.entities.list()->at(i));
        for(size_t i=0;i<births.size();++i)mortar_snapshot(row["effect_births"][i],*births[i]);
    }
};
J run_mortar_plants(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    MortarPlantsProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
        if(argc!=3)throw std::invalid_argument("usage: mortar_plants72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("mortar plant fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_mortar_plants(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
