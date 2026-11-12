#define PVZ72_NATIVE_TICK_PROBE_EMBEDDED
#include "native_tick_probe.cpp"

namespace {
struct NativeClockProbe : NativeTickProbe {
    J clock_events=J::array();
    bool observe_clock=false;
    explicit NativeClockProbe(int64_t seed,double width,double splash):NativeTickProbe(seed,width,splash){}
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="clock_setup") {
            observe_clock=true;world.tick=op.at("engine");world.published_tick=op.at("published");budget.enabled=true;
        }else if(name=="clock_defer") {
            const auto unit=units.at(op.at("unit").get<size_t>());
            const auto behavior=op.at("behavior").get<std::string>();
            const auto attempts=std::make_shared<int>(0);
            result=budget.defer(source_ref(unit),"clock_probe",op.at("slot"),[this,unit,behavior,attempts] {
                HeroContext context(world,{Seat::plant,Seat::zombie,CombatPhase::summon,source_ref(unit),{}});
                const auto key=world.attack_key(Seat::plant,HeroHit::ash);
                const double amount=world.damage(Seat::plant,10.,HeroHit::ash);
                clock_events.push_back({world.tick,world.attack_tick(),key.attack,amount});
                ++*attempts;
                if(*attempts==1 && behavior=="throw_once")throw std::runtime_error("clock constructor retry");
                return *attempts!=1 || behavior!="false_once";
            });
        }else return NativeTickProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        NativeTickProbe::extra_snapshot(row);
        if(observe_clock)row["clock_bridge"]={{"events",clock_events},{"pending",budget.pending_count()},{"draining",budget.draining}};
    }
};
J run_native_clock(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    NativeClockProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
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
        if(argc!=3)throw std::invalid_argument("usage: native_clock72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("native clock fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_native_clock(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
