#define PVZ72_DEATH_PROBE_EMBEDDED
#include "death_probe.cpp"
#include "sim/typed/native_registry.h"
namespace {
MatchMode mode(const std::string& value) {
    if(value=="duel")return MatchMode::duel;if(value=="duo")return MatchMode::duo;
    if(value=="pve")return MatchMode::pve;if(value=="coop")return MatchMode::coop;
    throw std::invalid_argument("unknown fixture match mode");
}
struct RegistryProbe:DeathProbe {
    std::vector<NativeObject> registry_held;
    explicit RegistryProbe(int64_t seed):DeathProbe(seed){}
    NativeObject object(const J& v){return v.is_object()?NativeObject(plant_ref(v.at("plant").get<size_t>())):NativeObject(units.at(v.get<size_t>()));}
    J object_label(const NativeObject& object)const {
        if(const auto* u=std::get_if<ZombieRef>(&object))return index(*u);
        const auto& plant=std::get<PlantRef>(object);size_t n=0;
        for(const auto id:battle.plants.order()){if(battle.plants.at(id)==plant)return J{{"plant",n}};++n;}
        throw std::logic_error("unknown registry plant");
    }
    std::optional<TargetRoster> extra_targets()override {
        calls.push_back(J::array({"extras"}));before("extras");auto result=battle.omitted_targets();after("extras");return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="registry_set") {
            keys(op,{"op","key","target"});battle.native_objects.set(op.at("key"),object(op.at("target")));
        }else if(action=="registry_erase") {
            keys(op,{"op","key"});result=battle.native_objects.erase(op.at("key"));
        }else if(action=="registry_get"||action=="registry_hold") {
            keys(op,{"op","key"});if(auto r=battle.native_objects.get(op.at("key"))){result=object_label(*r);if(action=="registry_hold")registry_held.push_back(*r);}
        }else if(action=="registry_mode") {
            keys(op,{"op","value"});battle.mode=mode(op.at("value"));
        }else if(action=="registry_flags") {
            keys(op,{"op","unit","grave","orphan","hp"});auto& u=*units.at(op.at("unit").get<size_t>());
            if(op.contains("grave"))u.protection.grave=op["grave"];if(op.contains("orphan"))u.orphan_barrel=op["orphan"];if(op.contains("hp"))u.body.hp=op["hp"];
        }else if(action=="registry_collect") {
            keys(op,{"op"});result=J::array();for(const auto& t:battle.omitted_targets())result.push_back(label(t));
        }else if(action=="registry_scope") {
            keys(op,{"op","body","catch"});
            try{auto original=battle.targets;auto additions=battle.omitted_targets();FullTargetsScope scope(battle.targets,std::span<const CombatTarget>(additions),std::move(original));operations(op.at("body"));scope.close();}
            catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return DeathProbe::extra_operation(op,result);return true;
    }
    void extra_snapshot(J& row)override {
        DeathProbe::extra_snapshot(row);row["registry"]=J::array();row["registry_held"]=J::array();row["registry_flags"]=J::array();
        for(const auto& e:battle.native_objects.entries())row["registry"].push_back(J::array({e.key,object_label(e.object)}));
        for(const auto& e:registry_held)row["registry_held"].push_back(object_label(e));
        for(const auto& u:units)row["registry_flags"].push_back(J::array({u->protection.grave,u->orphan_barrel}));
        row["match_seats"]=J::array();for(const auto seat:seats_for(battle.mode))row["match_seats"].push_back(seat_name(seat));
    }
};
J run_registry(const J& j) {
    RegistryProbe p(j.value("seed",int64_t(1)));J base=j;const auto cfg=base.value("death_config",J::object());base.erase("death_config");keys(cfg,{"fast"});configure_doom(p,base);
    p.chain.sourced_fastpath=cfg.value("fast",true);p.chain.patch.bosses=p.bosses;p.chain.damage.adjust_amount=p.damage.adjust_amount;p.chain.damage.shield_first=p.damage.shield_first;p.chain.damage.watch_armor=p.damage.watch_armor;
    p.operations(j.at("operations"));return p.states;
}
}
int main(int argc,char** argv) {
    try{if(argc!=3)throw std::invalid_argument("usage: registry72_probe input.jsonl output.jsonl");std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
        if(!in||!out)throw std::runtime_error("registry fixture files");std::string line;while(std::getline(in,line))if(!line.empty())out<<run_registry(J::parse(line)).dump()<<'\n';if(!out)throw std::runtime_error("registry output");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
