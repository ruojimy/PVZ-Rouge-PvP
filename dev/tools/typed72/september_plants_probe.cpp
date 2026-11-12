#define PVZ72_PLANT_REGION_PROBE_EMBEDDED
#include "plant_region_probe.cpp"
#include "sim/typed/september_plants.h"
#include "sim/typed/sweet_taunts.h"

namespace {
struct SeptemberPlantsProbe : PlantRegionProbe,ContentUnitDamage,SeptemberPlantServices {
    SeatCommands commands;
    SeatPathTracking path_banks{battle,navigation,path_rules,sight,hero_flags,commands};
    SweetTaunts taunts{battle,navigation,path_banks,path_rules,false};
    ContentTargets target_dispatch;
    ContentQueries queries;
    SeptemberPlants september;
    J september_events=J::array();
    bool observe_september=false,gate_september=false;
    explicit SeptemberPlantsProbe(int64_t seed,double width,double splash)
        :PlantRegionProbe(seed,width,splash),target_dispatch(battle,static_cast<ContentUnitDamage&>(*this),collision,width),
         queries(battle,target_dispatch,taunts),september(battle,world_region,queries,target_dispatch,collision,*this){}
    void ordinary(size_t index,double facing,double amount)override{PlantRegionProbe::ordinary(index,facing,amount);}
    void surface(size_t index,double facing,double amount)override{PlantRegionProbe::surface(index,facing,amount);}
    void september_event(const SeptemberPlantEvent& event)override {
        const auto name=event.kind==SeptemberPlantEvent::Kind::bloom?"gold_bloom":
                        event.kind==SeptemberPlantEvent::Kind::ghost_activated?"ghost_activated":"ghost_exploded";
        J fields={{"source",event.source.present() && !event.source.is_null()?J(event.source.get()):J(nullptr)}};
        if(event.kind==SeptemberPlantEvent::Kind::bloom){fields["suns"]=8;fields["amount"]=event.sun_amount;}
        september_events.push_back({name,fields});
        before("september_event");after("september_event");
    }
    void plant_gate(size_t index)override {
        PlantRegionProbe::plant_gate(index);
        if(gate_september)september.advance(battle.plant_roster->at(index));
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="september_setup")observe_september=true;
        else if(name=="september_configure")result=september.configure(plant_ref(op.at("plant").get<size_t>()),op.at("name").get<std::string>());
        else if(name=="september_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());const auto& fields=op.at("fields");
            read(fields,"_pvp_one_shot",plant.one_shot);read(fields,"_pvp_effect_done",plant.effect_done);
            read(fields,"_pvp_content_age",plant.content_age);read(fields,"_pvp_ghost_started",plant.ghost_started);
            read(fields,"_pvp_ghost_clock",plant.ghost_clock);read(fields,"_pvp_ghost_pulse",plant.ghost_pulse);
            read(fields,"_pvp_aura_factor",plant.aura_factor);
        }else if(name=="september_inside") {
            result=september.inside(plant_ref(op.at("plant").get<size_t>()),content_target(op.at("target")),
                                    op.at("horizontal"),op.at("vertical"));
        }else if(name=="september_tick" || name=="september_attack") {
            const auto plant=plant_ref(op.at("plant").get<size_t>());
            try {
                HeroContext scope(world,{Seat::zombie,Seat::plant,CombatPhase::plants,source_ref(plant),{}});
                NativeBirthScope births_scope(battle.runtime,static_cast<PlantRegionServices&>(*this));
                if(name=="september_tick")september.advance(plant);
                else september.attack(plant,op.at("amount"),op.at("horizontal"),op.at("vertical"),op.at("hero_amount"),hit(op.value("kind",J("content"))));
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="september_region") {
            gate_september=true;
            try {
                HeroContext scope(world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
                plants.run();
            }catch(const std::exception&) {
                gate_september=false;if(!op.value("catch",false))throw;result={{"caught",true}};
            }
            gate_september=false;
        }else return PlantRegionProbe::extra_operation(op,result);
        return true;
    }
    static void fields(J& record,const CombatPlant& plant) {
        write(record,"_pvp_one_shot",plant.one_shot);write(record,"_pvp_effect_done",plant.effect_done);
        write(record,"_pvp_content_age",plant.content_age);write(record,"_pvp_ghost_started",plant.ghost_started);
        write(record,"_pvp_ghost_clock",plant.ghost_clock);write(record,"_pvp_ghost_pulse",plant.ghost_pulse);
    }
    void extra_snapshot(J& row)override {
        PlantRegionProbe::extra_snapshot(row);
        if(!observe_september)return;
        J effects=J::array(),amounts=J::array();
        for(const auto& effect:september.effects)effects.push_back({effect.tick,{effect.point.x,effect.point.y}});
        for(const auto& sun:world_region.loose_suns)amounts.push_back(sun->bloom_amount?J(*sun->bloom_amount):J(nullptr));
        row["september"]={{"events",september_events},{"effects",effects},{"sun_amounts",amounts}};
        for(size_t i=0;i<all_plants.size();++i)fields(row["all_plants"][i],*all_plants[i]);
        for(size_t i=0;i<battle.plant_roster->size();++i)fields(row["plants"][i],*battle.plant_roster->at(i));
    }
};
J run_september_plants(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    SeptemberPlantsProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
        if(argc!=3)throw std::invalid_argument("usage: september_plants72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("September plant fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_september_plants(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
