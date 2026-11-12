#define PVZ72_CONTENT_ZOMBIES64_PROBE_EMBEDDED
#include "content_zombies64_probe.cpp"
#include "sim/typed/native_summons.h"

namespace {
struct NativeSummonsProbe : ContentZombie64Probe,NativeSummonServices {
    NativeSummons summons{battle,budget,*this};
    bool observe_summons=false;
    J summon_events=J::array();
    explicit NativeSummonsProbe(int64_t seed,double width,double splash):ContentZombie64Probe(seed,width,splash){}
    ZombieRef spawn_content(const std::string& name,Point point,double facing,const ScriptedSpawnOrigin& parent)override {
        const auto child=ContentZombie64Probe::spawn_slime(name,point,facing,{parent,{}});
        return child?child->unit:ZombieRef{};
    }
    void content_summoned(const Field<std::string>& source,const std::string& entity,const std::string& card,Seat owner)override {
        ;
        ;;
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="content_summon_setup")observe_summons=true;
        else if(name=="content_summon_fields") {
            const auto unit=units.at(op.at("unit").get<size_t>());const auto& fields=op.at("fields");
            read64(*unit,fields);
            if(fields.contains("_pvp_barrel_position"))unit->barrel_position.set(std::make_shared<Motion>(motion(fields.at("_pvp_barrel_position"))));
        }else if(name=="content_summon_clear")budget.clear();
        else if(name=="content_summon") {
            try {
                result=summons.summon(units.at(op.at("unit").get<size_t>()),op.at("name").get<std::string>(),
                    op.value("thrown",false),op.value("offset",0.),op.value("defer",true));
            }catch(const std::exception&) {if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return ContentZombie64Probe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        ContentZombie64Probe::extra_snapshot(row);if(!observe_summons)return;
        J records=J::array();
        for(const auto& unit:units) {
            J fields=J::object();write(fields,"旋转",unit->native.rotation);
            if(unit->barrel_position.present())fields["_pvp_barrel_position"]=as_json(*unit->barrel_position.get());
            records.push_back(fields);
        }
        row["native_summons"]={{"events",summon_events},{"units",records}};
    }
};
J run_summons(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    NativeSummonsProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: native_summons72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("content summon fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_summons(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
