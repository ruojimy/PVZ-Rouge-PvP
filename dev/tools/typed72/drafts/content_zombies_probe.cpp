#define PVZ72_NATIVE_STATUS_PROBE_EMBEDDED
#include "native_status_probe.cpp"
#include "sim/typed/content_zombies.h"
#include "sim/typed/cart_lifecycle.h"
#include "core/pymath.h"
#include <map>

namespace {
// Real content gate/finish, cart clocks, PvP64, scarecrows, queries and summons.
// Remaining controllers are observable boundaries, not release substitutes.
struct ContentZombiesProbe : NativeStatusProbe,ContentZombieControllers,CartLifecycleServices,
                             NativeSummonServices,ScarecrowServices {
    NativeContentZombieRules content_rules;
    uint64_t content_revision=0;
    CartLifecycle carts{battle,*this};
    NativeSummons summons{battle,budget,*this};
    Scarecrows scarecrows{battle,sight,*this};
    ContentZombies controller{battle,content_rules,tick_state.present,commands,hero_flags,path_banks,
        content_revision,queries,target_dispatch,taunts,content64,scarecrows,summons,*this,tick_state.drawing};
    J content_events=J::array(),summon_events=J::array(),cart_events=J::array();
    std::map<std::string,double> content_heights;
    bool content_seen=false,installed=false;
    double movement=1.,bite=1.,scale=1.;
    explicit ContentZombiesProbe(int64_t seed,double width,double splash):NativeStatusProbe(seed,width,splash){}
    void event(const std::string& name,const ZombieRef& unit,J extra=J::array()) {
        J row=J::array({name,index(unit)});for(const auto& value:extra)row.push_back(value);
        content_events.push_back(row);before("content_"+name);after("content_"+name);
    }
    void cart_before(const ZombieRef& unit)override {event("cart_before",unit);carts.before(unit);}
    void cart_animate(const ZombieRef& unit,bool active,bool fired)override {
        event("cart_animate",unit,J::array({active,fired}));carts.animate(unit,active,fired);
    }
    void september_gate(const ZombieRef& unit)override {event("september_gate",unit);}
    void september_wave_chase(const ZombieRef& unit)override {event("wave_chase",unit);}
    void september_finish(const ZombieRef& unit)override {event("september_finish",unit);}
    void zombies56_gate(const ZombieRef& unit)override {event("zombies56_gate",unit);}
    void zombies56_finish(const ZombieRef& unit)override {event("zombies56_finish",unit);}
    void zombies70_gate(const ZombieRef& unit)override {event("zombies70_gate",unit);}
    bool solid(Point point)const override {
        const auto row=int64_t(std::floor(point.y/battle.runtime.tile));
        if(row<0)return false;if(uint64_t(row)>=sight.solid.size())return true;
        const auto& cells=sight.solid.at(size_t(row));
        return cells.at(size_t(std::floor(pvz::py::mod(point.x,battle.world_width.get())/battle.runtime.tile))%cells.size())!=0;
    }
    void barrel_correct_pair(const ZombieRef& unit)override {event("barrel_correct",unit);}
    void barrel_detach(const ZombieRef& unit,double remaining)override {event("barrel_detach",unit,J::array({remaining}));}
    void barrel_break(const ZombieRef& unit)override {event("barrel_break",unit);}
    void barrel_move(const ZombieRef& unit,double factor)override {event("barrel_move",unit,J::array({factor}));}
    void barrel_contact(const ZombieRef& unit,double factor)override {event("barrel_contact",unit,J::array({factor}));}
    double bite_damage(const ZombieRef& unit,const ContentTarget& target)override {
        event("bite",unit,J::array({content_label(target)}));return bite;
    }
    double movement_factor(const ZombieRef&)const override {return movement;}
    void alias_art(const std::string& first,const std::string& second)override {ContentZombie64Probe::alias_art(first,second);}
    void tint_poison(const ZombieRef& unit)override {event("tint",unit);}
    double image_height(const std::string& key)const override {return content_heights.at(key);}
    double unit_scale(const ZombieRef&)const override {return scale;}
    void stun_star(Point point,Point dimensions)override {
        content_events.push_back({"star",{point.x,point.y},{dimensions.x,dimensions.y}});
        before("content_star");after("content_star");
    }
    void draw_content_zombie(const ZombieRef& unit)override {event("draw",unit);}
    void cart_expired(const Field<std::string>& entity,const Field<std::string>& card,double seconds)override {
        cart_events.push_back({"cart_expired",{{"entity",nullable(entity)},{"card",nullable(card)},{"seconds",seconds}}});
        before("cart_expired");after("cart_expired");
    }
    ZombieRef spawn_content(const std::string& name,Point point,double facing,const ScriptedSpawnOrigin& parent)override {
        const auto child=ContentZombie64Probe::spawn_slime(name,point,facing,{parent,{}});
        return child?child->unit:ZombieRef{};
    }
    void content_summoned(const Field<std::string>& source,const std::string& entity,const std::string& card,Seat owner)override {
        summon_events.push_back({"content_summon",{{"source",nullable(source)},{"entity",entity},{"card",card},{"owner",seat_name(owner)}}});
        before("content_summon_event");after("content_summon_event");
    }
    std::optional<std::string> spawn_echo_crow(Point,double,const std::string&)override {
        throw std::logic_error("echo outside gate/finish fixture");
    }
    void crow_echo_event(const std::string&,const Field<std::string>&,const std::string&)override {
        throw std::logic_error("echo event outside gate/finish fixture");
    }
    void finish_content_zombie()override {
        NativeTickProbe::finish_content_zombie();if(installed)controller.finish();
    }
    void release_pending_destination()override {
        NativeTickProbe::release_pending_destination();if(installed)controller.release_pending_destination();
    }
    void zombie_gate(size_t index)override {
        if(installed)controller.finish();NativeTickProbe::zombie_gate(index);if(installed)controller.gate(index);
    }
    void fields(const ZombieRef& unit,const J& value) {
        read64(*unit,value);auto& state=unit->content;
        read(value,"_pvp_saved_basketball_cd",state.saved_basketball_cd);
        read(value,"_pvp_summon_clock",state.summon_clock);read(value,"_pvp_cannon_rate",state.cannon_rate);
        read(value,"_pvp_cart_deadline",state.cart_deadline);read(value,"_pvp_cannon_anim",state.cannon_animation);
        read(value,"_pvp_cannon_recoil",state.cannon_recoil);read(value,"_pvp_cart_expired",state.cart_expired);
        read(value,"_pvp_cannon_loaded",state.cannon_loaded);read(value,"_pvp_barrel_direction",state.barrel_direction);
        read(value,"_pvp_barrel_remaining",state.barrel_remaining);read(value,"_pvp_barrel_broken",state.barrel_broken);
        read(value,"_pvp_barrel_discarded",state.barrel_discarded);read(value,"_pvp_barrel_detached",state.barrel_detached);
        read(value,"_pvp_target",state.target);read(value,"_pvp_hop_clock",unit->hop_clock);read(value,"_pvp_walk_speed",unit->walk_speed);
        read(value,"_pvp_blown",unit->body.blown);read(value,"_pvp_poison_killed",unit->poison.killed);
        read(value,"_pvp_zs_locked",unit->protection.locked);
        if(value.contains("_pvp_zs_lock_done"))unit->protection.lock_done=value.at("_pvp_zs_lock_done");
        if(value.contains("_pvp_content_position_before"))unit->grenadier.before.set(motion(value.at("_pvp_content_position_before")));
    }
    bool extra_operation(const J& op,J& result)override {
        const auto name=op.at("op").get<std::string>();
        if(name=="content_zombies_setup") {
            content_seen=true;installed=op.value("installed",false);
            content_rules.custom_zombies=op.at("custom").get<std::vector<std::string>>();
            content_heights=op.at("heights").get<decltype(content_heights)>();
            for(const auto& [key,height]:content_heights)if(key.ends_with("-帧0"))collision.flyer_image_height[key.substr(0,key.size()-5)]=height;
            movement=op.value("movement",1.);bite=op.value("bite",1.);scale=op.value("scale",1.);
        }else if(name=="content_zombie_fields") {
            const auto unit=units.at(op.at("unit").get<size_t>());fields(unit,op.at("fields"));
            for(const auto& key:op.value("erase",std::vector<std::string>{})) {
                if(key=="魅惑")unit->source.charmed.erase();else if(key=="灰烬")unit->body.ash.erase();
                else if(key=="_pvp_blown")unit->body.blown.erase();else if(key=="_pvp_ai_player_position")unit->content.player_position.erase();
                else if(key=="_pvp_card")unit->protection.card.erase();else if(key=="_pvp_saved_basketball_cd")unit->content.saved_basketball_cd.erase();
                else throw std::invalid_argument("unknown content erase");
            }
        }else if(name=="content_borrow") {
            const auto unit=units.at(op.at("unit").get<size_t>());
            if(!unit->content.player_position.present())unit->content.player_position=world.globals.position;
            world.globals.position.set(std::make_shared<Motion>(motion(op.at("position"))));
        }else if(name=="content_player_write")world.globals.position.get()->x=op.at("x");
        else if(name=="content_orders") {
            commands.shared=op.at("command")=="follow"?PathMode::follow_hero:PathMode::attack_plants;
            for(const auto& [seat,command]:op.at("commands").items())
                commands.by_seat[seat_index(parse_seat(seat))]=command=="follow"?PathMode::follow_hero:PathMode::attack_plants;
        }else if(name=="content_flag") {
            const auto seat=parse_seat(op.at("side").get<std::string>());std::optional<Point> point;
            if(!op.at("point").is_null())point=Point{op.at("point").at(0),op.at("point").at(1)};
            if(battle.mode==MatchMode::duo)hero_flags.by_seat[seat_index(seat)]=point;
            if(seat==Seat::zombie || battle.mode!=MatchMode::duo)hero_flags.shared=point;
        }else if(name=="content_drawing")tick_state.drawing=op.at("draw");
        else if(name=="content_scarecrow")result=scarecrows.configure(units.at(op.at("unit").get<size_t>()),op.at("name").get<std::string>(),op.at("hp"));
        else if(name=="content_gate" || name=="content_finish" || name=="content_release" || name=="content_cart_configure" || name=="content_cart_before" || name=="content_cart_animate") {
            try {
                const auto unit=op.contains("unit")?units.at(op.at("unit").get<size_t>()):ZombieRef{};
                if(name=="content_gate") {
                    size_t at=0;while(at<battle.targets->size() && battle.targets->at(at).unit!=unit)++at;
                    world.source_index=int64_t(at);controller.gate(at);
                }else if(name=="content_finish")controller.finish();
                else if(name=="content_release")controller.release_pending_destination();
                else if(name=="content_cart_configure")carts.configure(unit,op.at("card").get<std::string>());
                else if(name=="content_cart_before")carts.before(unit);
                else carts.animate(unit,op.at("active"),op.at("fired"));
            }catch(const std::exception&){if(!op.value("catch",false))throw;result={{"caught",true}};}
        }else return NativeStatusProbe::extra_operation(op,result);
        return true;
    }
    void extra_snapshot(J& row)override {
        NativeStatusProbe::extra_snapshot(row);if(!content_seen)return;
        J records=J::array(),identities=J::array();std::map<const Motion*,size_t> position_ids;
        auto identity=[&](const Field<std::shared_ptr<Motion>>& value)->J {
            if(!value.present() || value.is_null())return nullptr;
            return position_ids.try_emplace(value.get().get(),position_ids.size()).first->second;
        };
        identities.push_back(identity(world.globals.position));
        for(size_t seat=0;seat<4;++seat)if(world.heroes[seat])identities.push_back({seat_name(Seat(seat)),identity(world.heroes[seat]->frame.position)});
        for(const auto& unit:units) {
            const auto& state=unit->content;J item=J::object();
            if(state.player_position.present())item["_pvp_ai_player_position"]=state.player_position.is_null()?J(nullptr):as_json(*state.player_position.get());
            identities.push_back(identity(state.player_position));
            write(item,"_pvp_saved_basketball_cd",state.saved_basketball_cd);write(item,"_pvp_summon_clock",state.summon_clock);
            write(item,"_pvp_cannon_rate",state.cannon_rate);write(item,"_pvp_cart_deadline",state.cart_deadline);
            write(item,"_pvp_cannon_anim",state.cannon_animation);write(item,"_pvp_cannon_recoil",state.cannon_recoil);
            write(item,"_pvp_cart_expired",state.cart_expired);write(item,"_pvp_cannon_loaded",state.cannon_loaded);
            write(item,"_pvp_barrel_direction",state.barrel_direction);write(item,"_pvp_barrel_remaining",state.barrel_remaining);
            write(item,"_pvp_barrel_broken",state.barrel_broken);write(item,"_pvp_barrel_discarded",state.barrel_discarded);
            write(item,"_pvp_barrel_detached",state.barrel_detached);write(item,"_pvp_target",state.target);
            write(item,"_pvp_blown",unit->body.blown);write(item,"_pvp_hop_clock",unit->hop_clock);write(item,"_pvp_walk_speed",unit->walk_speed);
            write(item,"_pvp_zs_locked",unit->protection.locked);item["_pvp_zs_lock_done"]=unit->protection.lock_done;
            if(unit->grenadier.before.present())item["_pvp_content_position_before"]=as_json(unit->grenadier.before.get());
            #define CONTENT_NATIVE(n,k) write(item,k,unit->native.n);
            PVZ72_ZOMBIE_NATIVE_NUMBERS(CONTENT_NATIVE)
            #undef CONTENT_NATIVE
            write(item,"篮球",unit->protection.basketball);records.push_back(item);
        }
        row["content_zombies"]={{"last",controller.last()?J(index(controller.last())):J(nullptr)},
            {"events",content_events},{"summons",summon_events},{"carts",cart_events},{"units",records},{"identities",identities}};
    }
};
J run_content_zombies(const J& input) {
    J base=input;const auto cfg=base.at("world_rules");base.erase("world_rules");
    ContentZombiesProbe probe(input.value("seed",int64_t(1)),cfg.at("width"),cfg.value("splash",20./3.));
    configure_shooting(probe,base);probe.battle.world_width.set(cfg.at("width"));probe.battle.dense_planting=cfg.at("dense");
    probe.battle.protection.deathmatch=cfg.at("deathmatch");
    if(cfg.at("rage").get<bool>()){probe.battle.protection.secrets.team.set(size_t(DamageSecret::rage));probe.battle.protection.secrets.enabled=true;}
    probe.rules.damaging=cfg.at("damaging").get<std::vector<std::string>>();probe.rules.thrown=cfg.at("thrown").get<std::vector<std::string>>();
    probe.rules.homing_height=cfg.at("heights").get<decltype(probe.rules.homing_height)>();
    probe.collision.unit_scale=cfg.at("scale").get<decltype(probe.collision.unit_scale)>();
    probe.operations(input.at("operations"));return probe.states;
}
}
#ifndef PVZ72_CONTENT_ZOMBIES_PROBE_EMBEDDED
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::invalid_argument("usage: content_zombies72_probe inputs output");
        std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
        if(!input||!output)throw std::runtime_error("content zombies fixture streams");
        std::string line;while(std::getline(input,line))if(!line.empty())output<<run_content_zombies(J::parse(line)).dump()<<'\n';
        return output?0:2;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
#endif
