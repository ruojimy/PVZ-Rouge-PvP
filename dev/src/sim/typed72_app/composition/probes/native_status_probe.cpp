#define PVZ72_NATIVE_TICK_PROBE_EMBEDDED
#include "native_tick_probe.cpp"
#include "sim/typed/native_status.h"

namespace {
struct NativeStatusProbe : NativeTickProbe,NativeStatusServices {
    NativeStatus poison{battle,*this};
    J poison_events=J::array();
    bool observe_poison=false;
    std::vector<Seat> avatar_order()const {
        std::vector<Seat> order;
        for(size_t index=0;index<world.heroes.size();++index)if(world.heroes[index])order.push_back(Seat(index));
        return order;
    }
    explicit NativeStatusProbe(int64_t seed,double width,double splash):NativeTickProbe(seed,width,splash){}
    void status_tick()override {
        NativeTickProbe::status_tick();poison.tick(avatar_order());
    }
    void poison_damage(const Field<std::string>& entity,double amount,int level)override {
        ;
        ;;
    }
    void break_poisoned_barrel(const ZombieRef& unit)override {
        ;;;
    }
    void detach_poisoned_barrel(const ZombieRef& unit)override {
        ;;;
    }
    static void read_poison(const J& object,PoisonSlot& slot) {
        if(object.is_null()){slot.set_null();return;}
        auto state=std::make_shared<PoisonState>();
        read(object,"level",state->level);read(object,"until",state->until);read(object,"next",state->next);
        if(object.contains("owner"))state->owner.set(parse_seat(object.at("owner").get<std::string>()));
        if(object.contains("layers")) {
            if(object.at("layers").is_null())state->layers.set_null();
            else {
                auto layers=std::make_shared<PoisonLayers>();
                for(const auto& pair:object.at("layers")) {
                    const auto& layer=pair.at(1);
                    layers->emplace_back(pair.at(0).get<int>(),std::make_shared<PoisonLayer>(PoisonLayer{
                        layer.at("until"),layer.at("next"),parse_seat(layer.at("owner").get<std::string>())}));
                }
                state->layers.set(layers);
            }
        }
        slot.set(state);
    }
    static J poison_json(const PoisonSlot& slot) {
        if(!slot.present())return J{{"present",false}};
        if(slot.is_null())return nullptr;
        const auto& state=*slot.get();J result=J::object();
        write(result,"level",state.level);write(result,"until",state.until);write(result,"next",state.next);
        if(state.owner.present())result["owner"]=seat_name(state.owner.get());
        if(state.layers.present()) {
            if(state.layers.is_null())result["layers"]=nullptr;
            else {
                auto values=J::array();
                for(const auto& [level,layer]:*state.layers.get())values.push_back({level,
                    {{"until",layer->until},{"next",layer->next},{"owner",seat_name(layer->owner)}}});
                result["layers"]=values;
            }
        }
        return result;
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="poison_setup")observe_poison=true;
        else if(name=="poison_apply") {
            ContentTarget target=op.contains("side")?
                ContentTarget(CombatTarget::player(parse_seat(op.at("side").get<std::string>()))):
                ContentTarget(CombatTarget::zombie(units.at(op.at("unit").get<size_t>())));
            if(op.contains("side"))world.proxy(std::get<CombatTarget>(target).hero);
            poison.apply(target,op.at("level"),op.value("duration",4.),parse_seat(op.value("owner",std::string("plant"))));
        }else if(name=="poison_fields") {
            auto& slot=op.contains("side")?world.hero(parse_seat(op.at("side").get<std::string>())).poison:
                units.at(op.at("unit").get<size_t>())->poison.poison;
            if(op.value("erase",false))slot.erase();else read_poison(op.at("state"),slot);
        }else if(name=="poison_tick") {
            world.tick=op.at("tick");poison.tick(avatar_order());
        }else if(name=="poison_clock")world.tick=op.at("tick");
        else return NativeTickProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        NativeTickProbe::extra_snapshot(row);if(!observe_poison)return;
        J unit_states=J::array(),hero_states=J::object();
        for(const auto& unit:units) {
            const auto& state=unit->poison;J item={{"poison",poison_json(state.poison)}};
            write(item,"_pvp_poison_killed",state.killed);write(item,"_pvp_armor_triggered",state.armor_triggered);
            write(item,"_pvp_imp_armor",state.imp_armor);write(item,"_pvp_imp_armor_hp",state.imp_armor_hp);
            unit_states.push_back(item);
        }
        for(const auto seat:avatar_order()) {
            const auto& slot=world.hero(seat).poison;
            const auto name=std::string(seat_name(seat));
            hero_states[name]=poison_json(slot);
            if(slot.present()) {
                J raw=poison_json(slot);
                if(raw.is_object()&&raw.contains("layers")&&!raw["layers"].is_null()) {
                    J layers=J::object();
                    for(const auto& pair:raw["layers"])layers[std::to_string(pair.at(0).get<int>())]=pair.at(1);
                    raw["layers"]=std::move(layers);
                }
                row["heroes"][name]["_pvp_poison"]=std::move(raw);
            }
        }
        row["poison"]={{"units",unit_states},{"heroes",hero_states},{"events",poison_events}};
    }
};
J run_native_status(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    NativeStatusProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_NATIVE_STATUS_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: native_status72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("native status fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_native_status(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
