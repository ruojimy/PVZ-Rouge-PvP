#define PVZ72_PLANT_REGION_PROBE_EMBEDDED
#include "plant_region_probe.cpp"
#include "sim/typed/plant_aim.h"

namespace {
struct PlantAimProbe : PlantRegionProbe {
    PeaHybrid hybrid{battle,chart,indexes};
    bool hybrid_enabled=false;
    bool observe_hybrid=false;
    bool hybrid_gate_enabled=false;
    explicit PlantAimProbe(int64_t seed,double width,double splash):PlantRegionProbe(seed,width,splash){}
    void add_entity(std::string name,double facing,Motion point)override {
        const auto source=world.source();
        const auto found=std::find_if(all_plants.begin(),all_plants.end(),[&](const auto& plant){return source_ref(plant)==source;});
        const PlantRef captured=found==all_plants.end()?PlantRef{}:*found;
        const auto first=battle.runtime.entities.list()->size();
        PlantRegionProbe::add_entity(std::move(name),facing,point);
        hybrid.after_birth(captured,first);
    }
    void plant_gate(size_t index)override {
        PlantRegionProbe::plant_gate(index);
        if(!hybrid_gate_enabled)return;
        hybrid.restore();chart.restore();
        const auto source=battle.plant_roster->at(index);
        chart.begin(TrackingSource::from(source));
        hybrid.gate(source,hybrid_enabled);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="hybrid_setup") {
            observe_hybrid=true;hybrid_enabled=op.at("enabled");
        }else if(name=="hybrid_fields") {
            auto& plant=*plant_ref(op.at("plant").get<size_t>());
            const auto& fields=op.at("fields");
            read(fields,"angle",plant.pea_angle);
            if(fields.contains("split")) {
                if(fields.at("split").is_null())plant.split_pea_angles.set_null();
                else {
                    std::array<Field<double>,2> angles;
                    read(fields.at("split"),"1",angles[0]);read(fields.at("split"),"-1",angles[1]);
                    plant.split_pea_angles.set(std::move(angles));
                }
            }
        }else if(name=="hybrid_gate") {
            try{hybrid.gate(op.at("plant").is_null()?PlantRef{}:plant_ref(op.at("plant").get<size_t>()),hybrid_enabled);}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="hybrid_query") {
            std::vector<Point> centers;
            for(const auto& p:op.at("centers"))centers.push_back({p.at(0),p.at(1)});
            const auto plant=plant_ref(op.at("plant").get<size_t>());
            const auto selected=pick_tripea_targets(battle,chart,plant,plant->facing,centers);
            result=J::array();
            for(const auto& target:selected) {
                if(target)result.push_back({target->index,label(target->target),{target->point.x,target->point.y}});
                else result.push_back(nullptr);
            }
        }else if(name=="hybrid_birth") {
            try {
                const auto source=plant_ref(op.at("plant").get<size_t>());
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,source_ref(source),{}});
                add_entity(op.at("name"),op.at("facing"),motion(op.at("point")));
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else if(name=="hybrid_region") {
            hybrid_gate_enabled=true;
            try {
                HeroContext context(world,{Seat::zombie,Seat::plant,CombatPhase::plants,{},{}});
                try{plants.run();}catch(...){hybrid.restore();chart.restore();throw;}
                hybrid.restore();chart.restore();
            }catch(const std::exception&){
                hybrid_gate_enabled=false;if(!op.value("catch",false))throw;result={{"caught",true}};
            }
            hybrid_gate_enabled=false;
        }else return PlantRegionProbe::extra_operation(op,result);
        return true;
    }
    static void aim_fields(J& record,const CombatPlant& plant) {
        write(record,"_pvp_pea_angle",plant.pea_angle);
        if(plant.split_pea_angles.present()) {
            J angles=nullptr;
            if(!plant.split_pea_angles.is_null()) {
                angles=J::object();
                write(angles,"1",plant.split_pea_angles.get()[0]);write(angles,"-1",plant.split_pea_angles.get()[1]);
            }
            record["_pvp_split_pea_angles"]=std::move(angles);
        }
    }
    void extra_snapshot(J& row)override {
        PlantRegionProbe::extra_snapshot(row);
        if(!observe_hybrid)return;
        row["hybrid_active"]=hybrid.active();
        for(size_t i=0;i<all_plants.size();++i)aim_fields(row["all_plants"][i],*all_plants[i]);
        for(size_t i=0;i<battle.plant_roster->size();++i)aim_fields(row["plants"][i],*battle.plant_roster->at(i));
    }
};
J run_plant_aim(const J& input) {
    J base=input;
    const auto cfg=base.at("world_rules");base.erase("world_rules");
    PlantAimProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
        if(argc!=3)throw std::invalid_argument("usage: plant_aim72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);
        std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("plant aim fixture streams");
        std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_plant_aim(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
