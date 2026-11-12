// Reuse the cold hero fixture codecs; this file is never a game dependency.
#define PVZ72_PROBE_EMBEDDED
#include "hero_probe.cpp"
namespace {
Zombie body(const J& j) {
    keys(j,{"僵尸","防具","手持","血量","防具血量","手持血量","方向","位置","受伤","手持受伤","灰烬","气球"});
    Zombie z;z.kind=j.at("僵尸");z.armor=j.at("防具");z.hand=j.at("手持");z.hp=j.at("血量");z.armor_hp=j.at("防具血量");
    z.hand_hp=j.at("手持血量");z.facing=j.at("方向");z.motion=motion(j.at("位置"));z.hurt=j.at("受伤");z.hand_hurt=j.at("手持受伤");
    read(j,"灰烬",z.ash);read(j,"气球",z.balloon);return z;
}
J body_state(const Zombie& z) {
    J j={{"僵尸",z.kind},{"防具",z.armor},{"手持",z.hand},{"血量",z.hp},{"防具血量",z.armor_hp},
         {"手持血量",z.hand_hp},{"方向",z.facing},{"位置",as_json(z.motion.get())},{"受伤",z.hurt},{"手持受伤",z.hand_hurt}};
    write(j,"灰烬",z.ash);write(j,"气球",z.balloon);return j;
}
struct TargetProbe : Probe,RawDamageChain {
    TargetDamage damage;
    std::vector<ZombieRef> units;
    std::vector<TypedBattleState::UnitId> ids;
    std::vector<std::string> bosses;
    std::shared_ptr<TargetRoster> original_roster=battle.targets;
    J raw_calls=J::array(),armor_events=J::array();
    bool throw_raw=false,throw_watch=false;
    explicit TargetProbe(int64_t seed,bool adjust):Probe(seed),damage(world,battle.protection,*this){damage.adjust_amount=adjust;}
    size_t index(const ZombieRef& unit) const {
        for(size_t i=0;i<units.size();++i)if(units[i]==unit)return i;throw std::logic_error("unknown fixture unit");
    }
    CombatTarget target(const J& j) {
        if(j.is_string()){const auto seat=parse_seat(j.get<std::string>());world.proxy(seat);return CombatTarget::player(seat);}
        return CombatTarget::zombie(units.at(j.get<size_t>()));
    }
    J label(const CombatTarget& target)const{return target.is_hero()?J(seat_name(target.hero)):J(index(target.unit));}
    std::shared_ptr<AttackSource> selected_source(const J& op)override {
        return op.contains("unit_source")?source_ref(units.at(op["unit_source"].get<size_t>())):Probe::selected_source(op);
    }
    HitResult ordinary(const ZombieRef& unit,double facing,double amount)override {
        raw_calls.push_back(J::array({"ordinary",index(unit),facing,amount}));
        damage_zombie(visual,unit->body,facing,amount);
        if(throw_raw)throw std::runtime_error("injected raw callback failure");return {};
    }
    HitResult surface(const ZombieRef& unit,double facing,double amount)override {
        raw_calls.push_back(J::array({"surface",index(unit),facing,amount}));
        const auto r=surface_hand_damage(visual,unit->body,facing,amount);
        if(r==SurfaceDamageResult::armorless)damage.ordinary(CombatTarget::zombie(unit),facing,amount);
        if(throw_raw)throw std::runtime_error("injected raw callback failure");return HitResult::flag(r==SurfaceDamageResult::hand_hit);
    }
    HitResult ash(const ZombieRef& unit)override {
        raw_calls.push_back(J::array({"ash",index(unit)}));auto& z=unit->body;
        if(z.hp+z.armor_hp>500.)damage.ordinary(CombatTarget::zombie(unit),1.,std::find(bosses.begin(),bosses.end(),z.kind)!=bosses.end()?300.:500.);
        else z.ash.set(0.);
        if(throw_raw)throw std::runtime_error("injected raw callback failure");return {};
    }
    void armor_broken(const ZombieRef& unit,ArmorSlot slot,const std::string& kind,double maximum)override {
        armor_events.push_back(J::array({index(unit),slot==ArmorSlot::head?"防具":"手持",kind,maximum}));
        if(throw_watch)throw std::runtime_error("injected armor callback failure");
    }
    bool extra_operation(const J& op,J& result)override {
        const std::string action=op.at("op");
        if(action=="unit_hit") {
            keys(op,{"op","target","kind","facing","amount","throw_raw","throw_watch","catch"});
            const auto t=target(op.at("target"));const std::string kind=op.at("kind");
            throw_raw=op.value("throw_raw",false);throw_watch=op.value("throw_watch",false);HitResult hit;
            try {
                if(kind=="ordinary")hit=damage.ordinary(t,op.value("facing",1.),op.at("amount"));
                else if(kind=="surface")hit=damage.surface(t,op.value("facing",1.),op.at("amount"));
                else if(kind=="ash")hit=damage.ash(t);
                else throw std::invalid_argument("unknown hit kind");
                if(hit.kind==HitResult::Kind::none)result=nullptr;else if(hit.kind==HitResult::Kind::boolean)result=hit.value!=0.;else result=hit.value;
            }catch(const std::runtime_error&){if(!op.value("catch",false))throw;result={{"caught",true}};}
            throw_raw=false;throw_watch=false;
        } else if(action=="expose") {
            keys(op,{"op","extras","body","provider"});TargetRoster extras;for(const auto& item:op.at("extras"))extras.push_back(target(item));
            FullTargetsScope scope(battle.targets,op.value("provider",true)?std::optional<std::span<const CombatTarget>>(extras):std::nullopt);
            operations(op.at("body"));scope.close();
        } else if(action=="roster_replace") {
            keys(op,{"op","targets"});auto roster=std::make_shared<TargetRoster>();for(const auto& t:op.at("targets"))roster->push_back(target(t));battle.targets=std::move(roster);
        } else if(action=="roster_append") {
            keys(op,{"op","target"});battle.targets->push_back(target(op.at("target")));
        } else if(action=="remove_unit") {
            keys(op,{"op","unit"});result=battle.remove_zombie(ids.at(op.at("unit").get<size_t>()));
        } else return false;
        return true;
    }
    void extra_snapshot(J& row)override {
        row["battle_units"]=J::array();row["packets"]=J::array();
        for(const auto& unit:units) {
            auto u=body_state(unit->body);const auto& s=unit->source;
            write(u,"_pvp_id",s.id);write(u,"_pvp_owner",s.owner);write(u,"魅惑",s.charmed);
            write(u,"_pvp_zs_hurt",unit->protection.hurt_tick);write(u,"_pvp_zs_relic_until",unit->protection.relic_until);
            write(u,"_pvp_reaper_hurt",unit->protection.reaper_hurt);write(u,"_pvp_zs_locked",unit->protection.locked);
            if(unit->chili_ash_hits.present())u["chili_hit_count"]=unit->chili_ash_hits.is_null()?J(nullptr):J(unit->chili_ash_hits.get().size());
            row["battle_units"].push_back(std::move(u));row["packets"].push_back(damage.has_packet(unit));
        }
        row["roster"]=J::array();for(const auto& t:*battle.targets)row["roster"].push_back(label(t));
        row["original_roster_identity"]=battle.targets==original_roster;
        row["raw_calls"]=raw_calls;row["armor_events"]=armor_events;row["entities"]=J::array();
        for(const auto& entity:*visual.entities.list()) {
            const auto& e=*entity;J j=source_state(e.source,e.motion.get(),e.flight);j["方向"]=e.facing;
            write(j,"牛顿",e.gravity);write(j,"消亡",e.expires);write(j,"穿墙",e.through_wall);row["entities"].push_back(std::move(j));
        }
        row["unit_events"]=J::array();row["ordered_events"]=J::array();
        for(const auto& e:visual.events){row["ordered_events"].push_back(event_state(e));if(std::holds_alternative<RelicEvent>(e))row["unit_events"].push_back(event_state(e));}
        // Immersive native sounds include their position; ordinary hero sound
        // calls above still use the original single-name presentation boundary.
        row["unit_sounds"]=J::array();for(const auto& s:visual.sounds)row["unit_sounds"].push_back(J::array({s.name,J::array({s.position.x,s.position.y})}));
    }
};
void configure_targets(TargetProbe& p,const J& j) {
    J base=j;base.erase("units");base.erase("damage");const auto cfg=j.value("damage",J::object());
    keys(cfg,{"adjust","watch_armor","shield_first","until","factor","cards","bosses","deathmatch","selected","hero_targets"});
    configure_probe(p,base);
    p.damage.watch_armor=cfg.value("watch_armor",false);p.damage.shield_first=cfg.value("shield_first",false);
    auto& policy=p.battle.protection;policy.secrets.configure(p.world.players);policy.until=cfg.value("until",0);policy.producer_factor=cfg.value("factor",1.);policy.deathmatch=cfg.value("deathmatch",false);
    const auto cards=cfg.value("cards",J::object());for(auto i=cards.begin();i!=cards.end();++i)policy.cards[i.key()]={i.value().get<bool>()};
    const auto selected=cfg.value("selected",J::object());for(auto i=selected.begin();i!=selected.end();++i)policy.selected_grave[seat_index(parse_seat(i.key()))]=i.value().is_null()?std::optional<std::string>{}:std::optional<std::string>(i.value().get<std::string>());
    p.bosses=cfg.value("bosses",std::vector<std::string>{});
    for(const auto& item:j.at("units")) {
        keys(item,{"body","source","state","armor_max","hand_max"});auto u=std::make_shared<CombatZombie>();u->body=body(item.at("body"));
        u->source=*source(item.value("source",J::object()));u->source.bind_zombie_kind(u->body.kind);
        read(item,"armor_max",u->armor_max);read(item,"hand_max",u->hand_max);
        const auto s=item.value("state",J::object());keys(s,{"_pvp_card","_pvp_hero","_pvp_grave","_pvp_anchor_until","_pvp_zs_hurt","_pvp_zs_crowd_factor","_pvp_zs_relic_until","篮球","_pvp_reaper_hurt","_pvp_zs_lock_done","_pvp_zs_locked"});
        read(s,"_pvp_card",u->protection.card);u->protection.hero=s.value("_pvp_hero",false);u->protection.grave=s.value("_pvp_grave",false);
        read(s,"_pvp_anchor_until",u->protection.anchor_until);read(s,"_pvp_zs_hurt",u->protection.hurt_tick);read(s,"_pvp_zs_crowd_factor",u->protection.crowd_factor);
        read(s,"_pvp_zs_relic_until",u->protection.relic_until);read(s,"篮球",u->protection.basketball);read(s,"_pvp_reaper_hurt",u->protection.reaper_hurt);
        u->protection.lock_done=s.value("_pvp_zs_lock_done",false);read(s,"_pvp_zs_locked",u->protection.locked);
        p.units.push_back(u);p.ids.push_back(p.battle.add_zombie(std::move(u)));
    }
    for(const auto& side:cfg.value("hero_targets",J::array()))p.battle.targets->push_back(p.target(side));
}
J run_targets(const J& j) {
    TargetProbe p(j.value("seed",int64_t(1)),j.value("damage",J::object()).value("adjust",true));
    configure_targets(p,j);p.operations(j.at("operations"));return p.states;
}
}
#ifndef PVZ72_TARGET_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: targets72_probe input.jsonl output.jsonl");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("cannot open target probe files");std::string line;
        while(std::getline(input,line))if(!line.empty())output<<run_targets(J::parse(line)).dump()<<'\n';
        if(!output)throw std::runtime_error("cannot write target results");return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
#endif
