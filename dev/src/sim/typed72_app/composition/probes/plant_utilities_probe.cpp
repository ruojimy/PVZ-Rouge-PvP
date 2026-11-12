#define PVZ72_PLANT_REGION_PROBE_EMBEDDED
#include "plant_region_probe.cpp"
#include "sim/typed/sea_shroom.h"
#include "sim/typed/owner_umbrella.h"

namespace {
struct PlantUtilitiesProbe : PlantRegionProbe,ContentUnitDamage {
    ContentTargets sea_damage;
    SeaShroom sea;
    std::shared_ptr<TargetBuckets> base_rows;
    bool observe_utilities=false;
    bool gate_sea=false;
    explicit PlantUtilitiesProbe(int64_t seed,double width,double splash)
        :PlantRegionProbe(seed,width,splash),sea_damage(battle,static_cast<ContentUnitDamage&>(*this),collision,width),
         sea(battle,indexes,sight,sea_damage){}
    void ordinary(size_t index,double facing,double amount)override{PlantRegionProbe::ordinary(index,facing,amount);}
    void surface(size_t index,double facing,double amount)override{PlantRegionProbe::surface(index,facing,amount);}
    void plant_gate(size_t index)override {
        PlantRegionProbe::plant_gate(index);
        if(gate_sea)sea.gate(battle.plant_roster->at(index));
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="plant_utilities_setup") {
            observe_utilities=true;
            base_rows=indexes.rows;
            sight.water=op.at("water").get<std::vector<std::vector<uint8_t>>>();
        }else if(name=="sea_gate")sea.gate(plant_ref(op.at("plant").get<size_t>()));
        else if(name=="sea_restore")sea.restore();
        else if(name=="sea_bubbles") {
            NativeBirthScope births_scope(battle.runtime,static_cast<PlantRegionServices&>(*this));
            sea.bubbles();
        }
        else if(name=="sea_region") {
            gate_sea=true;
            try {
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
                plants.run();
            }catch(...) {
                gate_sea=false;
                sea.restore();
                if(!op.value("catch",false))throw;
                result={{"caught",true}};
            }
            gate_sea=false;
            sea.restore();
        }else if(name=="owner_umbrella") {
            try{owner_umbrella_effects(battle,op.at("after").get<bool>(),seats_for(battle.mode));}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return PlantRegionProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        PlantRegionProbe::extra_snapshot(row);
        if(observe_utilities)row["plant_utilities"]={sea.active(),indexes.rows==base_rows};
    }
};
J run_plant_utilities(const J& input) {
    J base=input;
    const auto cfg=base.at("world_rules");base.erase("world_rules");
    PlantUtilitiesProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
        if(argc!=3)throw std::invalid_argument("usage: plant_utilities72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);
        std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("plant utility fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_plant_utilities(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
