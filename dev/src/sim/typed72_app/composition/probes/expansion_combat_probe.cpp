#define PVZ72_EXPANSION_GARDEN_PROBE_EMBEDDED
#include "expansion_garden_probe.cpp"
#include "sim/typed/expansion_combat.h"

namespace {
struct ExpansionProbe : GardenProbe,ExpansionCombatServices {
    PeaHybrid hybrid{battle,chart,indexes};
    ExpansionCombat expansion{battle,sight,hybrid,action_state.drawing,*this};
    J expansion_events=J::array();
    std::map<std::string,std::string> atlas,saved_atlas;
    std::set<CombatZombie*> barrels;
    bool expansion_seen=false,expansion_installed=false;
    explicit ExpansionProbe(int64_t seed,double width,double splash):GardenProbe(seed,width,splash){}
    HitResult expansion_inner_damage(size_t i,double facing,double amount)override {
        ;;
        const auto result=chain.damage.ordinary(battle.targets->at(i),facing,amount);
        ;return result;
    }
    void ordinary_damage(size_t i,double facing,double amount)override {
        if(expansion_installed)expansion.ordinary(i,facing,amount);
        else GardenProbe::ordinary_damage(i,facing,amount);
    }
    void expansion_outer_damage(size_t i,double facing,double amount)override{ordinary_damage(i,facing,amount);}
    bool expansion_barrel_active(const ZombieRef& unit)const override{return barrels.contains(unit.get());}
    void expansion_correct_barrel(const ZombieRef& unit)override{;}
    void black_armor_event(const std::string& variant,Point point)override{;}
    void expansion_armor_clear()override{;}
    void expansion_armor_gate(const ZombieRef& unit)override{;}
    void expansion_restore_art()override{for(const auto& [key,value]:saved_atlas)atlas[key]=value;saved_atlas.clear();}
    bool expansion_has_art(const std::string& key)const override{return atlas.contains(key);}
    void expansion_alias_one(const std::string& old,const std::string& next)override{saved_atlas[old]=atlas.at(old);atlas[old]=atlas.at(next);}
    void expansion_draw_pole(Point point)override{;}
    void finish_expansion_zombie()override {
        GardenProbe::finish_expansion_zombie();if(expansion_installed)expansion.finish_zombie();
    }
    void zombie_gate(size_t i)override {
        GardenProbe::zombie_gate(i);if(expansion_installed)expansion.zombie_gate(battle.targets->at(i).unit);
    }
    void add_entity(std::string name,double facing,Motion point)override {
        const auto first=visual.entities.list()->size();const auto captured=world.source();
        PlantRef plant;
        for(const auto& candidate:all_plants)if(captured.get()==&candidate->source){plant=candidate;break;}
        GardenProbe::add_entity(std::move(name),facing,point);
        if(expansion_installed)expansion.after_projectile(captured,plant,first,world.source_index);
    }
    static void state_fields(ExpansionCombatState& state,const J& fields) {
        read(fields,"_pvp_black_armor",state.black_armor);read(fields,"_pvp_before_vy",state.before_vy);
        read(fields,"_pvp_charge_until",state.charge_until);read(fields,"_pvp_charge_ready",state.charge_ready);
        read(fields,"_pvp_charge_cd",state.charge_cd);read(fields,"_pvp_charging",state.charging);
        read(fields,"_pvp_paralysis_until",state.paralysis_until);read(fields,"_pvp_paralysis_started",state.paralysis_started);
        read(fields,"_pvp_paralysis_garlic",state.paralysis_garlic);
    }
    static void state_snapshot(J& row,const ExpansionCombatState& state) {
        write(row,"_pvp_black_armor",state.black_armor);write(row,"_pvp_before_vy",state.before_vy);
        write(row,"_pvp_charge_until",state.charge_until);write(row,"_pvp_charge_ready",state.charge_ready);
        write(row,"_pvp_charge_cd",state.charge_cd);write(row,"_pvp_charging",state.charging);
        write(row,"_pvp_paralysis_until",state.paralysis_until);write(row,"_pvp_paralysis_started",state.paralysis_started);
        write(row,"_pvp_paralysis_garlic",state.paralysis_garlic);
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="expansion_setup") {
            expansion_seen=true;expansion_installed=op.value("installed",true);
            const auto secrets=op.value("secrets",J::object());
            for(size_t i=0;i<world.players.size();++i)if(world.players[i])world.players[i]->secrets=secrets.value(std::string(seat_name(Seat(i))),std::vector<std::string>{});
            expansion.configure_locked_secrets();
            atlas.clear();for(const auto& key:op.value("atlas",std::vector<std::string>{}))atlas[key]=key;
        }else if(name=="expansion_fields") {
            const auto target=this->target(op.at("target"));const auto& fields=op.at("fields");
            if(target.unit) {
                const auto& unit=target.unit;state_fields(unit->expansion,fields);
                read(fields,"_pvp_poison_killed",unit->poison.killed);read(fields,"_pvp_armor_triggered",unit->poison.armor_triggered);
                read(fields,"_pvp_variant",unit->source.variant);read(fields,"_pvp_base_speed",unit->base_speed);
                if(fields.contains("_pvp_orphan_barrel"))unit->orphan_barrel=fields.at("_pvp_orphan_barrel");
                read(fields,"大蒜",unit->native.garlic);read(fields,"移速",unit->native.move_speed);read(fields,"出场",unit->native.entry);
                read(fields,"眩晕",unit->body.stun);read(fields,"冰冻",unit->body.ice);read(fields,"黄油",unit->body.butter);
                if(fields.contains("防具"))unit->body.armor=fields.at("防具");
                if(fields.contains("防具血量"))unit->body.armor_hp=fields.at("防具血量");
                if(fields.contains("僵尸"))unit->body.kind=fields.at("僵尸");
                if(fields.contains("位置"))unit->body.motion=motion(fields.at("位置"));
                if(fields.contains("血量"))unit->body.hp=fields.at("血量");
                if(fields.contains("受伤"))unit->body.hurt=fields.at("受伤");
                read(fields,"撑杆",unit->body.pole_vault);
                if(op.value("barrel",false))barrels.insert(unit.get());
                for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                    if(key=="撑杆")unit->body.pole_vault.erase();else if(key=="_pvp_black_armor")unit->expansion.black_armor.erase();
                    else throw std::invalid_argument("expansion erase");
                }
            }else {
                auto& proxy=world.proxy(target.hero);state_fields(proxy.expansion,fields);read(fields,"大蒜",proxy.native.garlic);
                if(fields.contains("眩晕"))world.write_proxy_status(target.hero,HeroStatus::stun,fields.at("眩晕"));
            }
        }else if(name=="expansion_configure") {
            const auto& setup=op.at("setup");ExpansionVariantSetup values;
            values.name=op.at("variant");values.native_template=setup.at(0);values.hp=setup.at(1);values.armor=setup.at(2);
            values.armor_hp=setup.at(3);values.riding=setup.at(6);values.riding_hp=setup.at(7);
            expansion.configure(units.at(op.at("unit").get<size_t>()),values);
        }else if(name=="expansion_call") {
            const auto action=op.at("action").get<std::string>();
            if(action=="finish")expansion.finish_zombie();
            else if(action=="restore")expansion_restore_art();
            else if(action=="source")expansion.source_gate(op.contains("plant")?plant_ref(op.at("plant").get<size_t>()):PlantRef{},op.contains("entity")?births.at(op.at("entity").get<size_t>()):EntityRef{});
            else if(action=="hit") {
                const auto hit=expansion.ordinary(op.at("index"),op.value("facing",1.),op.at("amount"));
                result=hit.kind==HitResult::Kind::none?J(nullptr):hit.kind==HitResult::Kind::boolean?J(bool(hit.value)):J(hit.value);
            }else {
                const auto target=this->target(op.at("target"));
                if(action=="paralysis")expansion.apply_paralysis(target);
                else if(action=="recovery")expansion.paralysis_recovery(target);
                else if(action=="charge")expansion.charge(target.unit);
                else if(action=="gate")expansion.zombie_gate(target.unit);
                else if(action=="drop")expansion.armor_drop(target.unit);
                else if(action=="blast")expansion.black_armor_blast(target.unit,op.at("variant"));
                else if(action=="worn"){const auto value=expansion.worn_black_armor(target.unit);result=value?J(*value):J(nullptr);}
                else throw std::invalid_argument("expansion call");
            }
        }else return GardenProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        GardenProbe::extra_snapshot(row);if(!expansion_seen)return;
        J units=J::array(),heroes=J::object(),art=J::object();
        for(const auto& unit:this->units) {
            J state=J::object();state_snapshot(state,unit->expansion);
            write(state,"_pvp_variant",unit->source.variant);write(state,"_pvp_base_speed",unit->base_speed);
            write(state,"_pvp_poison_killed",unit->poison.killed);write(state,"_pvp_armor_triggered",unit->poison.armor_triggered);
            write(state,"_pvp_imp_armor",unit->poison.imp_armor);write(state,"_pvp_imp_armor_hp",unit->poison.imp_armor_hp);
            write(state,"大蒜",unit->native.garlic);write(state,"移速",unit->native.move_speed);write(state,"出场",unit->native.entry);
            write(state,"眩晕",unit->body.stun);write(state,"撑杆",unit->body.pole_vault);units.push_back(state);
        }
        for(size_t i=0;i<world.proxies.size();++i)if(world.proxies[i]) {
            J state=J::object();state_snapshot(state,world.proxies[i]->expansion);
            write(state,"大蒜",world.proxies[i]->native.garlic);const auto seat=std::string(seat_name(Seat(i)));heroes[seat]=state;
            state_snapshot(row["proxies"][seat],world.proxies[i]->expansion);
            write(row["proxies"][seat],"大蒜",world.proxies[i]->native.garlic);
        }
        for(const auto& [key,value]:atlas)if(key!=value)art[key]=value;
        row["expansion"]={{"units",units},{"heroes",heroes},{"events",expansion_events},{"atlas",art},
            {"last",expansion.last_zombie?J(index(expansion.last_zombie)):J(nullptr)}};
    }
};
J run_expansion(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ExpansionProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));
    probe.battle.dense_planting=cfg.at("dense");probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();
    probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    NativeBirthScope births(probe.battle.runtime,static_cast<ZombieMotionServices&>(probe));
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_EXPANSION_COMBAT_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: expansion_combat72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("expansion fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_expansion(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
