#include "sim/typed/hero.h"
#include "sim/typed/zombie_spawn.h"
#include "sim/typed/targets.h"
#include <algorithm>
#include <cmath>
#include <exception>

namespace pvz::typed72 {
namespace {
template<class T> void copy_present(Field<T>& to, const Field<T>& from) { if (from.present()) to = from; }
void copy_combat(HeroFrame& to, const HeroFrame& from) {
#define CP(n) copy_present(to.n,from.n);
    PVZ72_HERO_COMBAT(CP)
#undef CP
}
} // namespace
void HeroFrame::overlay(const HeroFrame& from, bool include_secrets) {
    auto& to=*this;
#define CP(n,k) copy_present(to.n,from.n);
    PVZ72_HERO_NUMBERS(CP) PVZ72_HERO_BOOLEANS(CP) PVZ72_HERO_STRINGS(CP)
#undef CP
    copy_present(to.position,from.position);
    if (include_secrets) copy_present(to.secrets,from.secrets);
}
namespace {
void copy_hurt(HeroFrame& to, const HeroFrame& from) {
    to.hp=from.hp; to.recovery=from.recovery; to.hurt=from.hurt; to.down=from.down;
}
bool has(const std::vector<std::string>& values, std::string_view key) {
    return std::find(values.begin(),values.end(),key)!=values.end();
}
bool secret(const HeroFrame& f, std::string_view name) {
    if (!f.secrets.present()) return false;
    return has(*f.secrets.get(),name);
}
std::string_view name(const Field<std::string>& f) { return f.present() && !f.is_null() ? f.get() : std::string_view{}; }
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
}
std::string_view seat_name(Seat s) {
    switch(s){case Seat::plant:return "plant";case Seat::zombie:return "zombie";case Seat::plant2:return "plant2";case Seat::zombie2:return "zombie2";}
    throw std::invalid_argument("invalid hero seat");
}
Seat parse_seat(std::string_view s) {
    if(auto seat=known_seat(s))return *seat;
    throw std::invalid_argument("unknown hero seat");
}
std::optional<Seat> known_seat(std::string_view s) {
    for(auto v:{Seat::plant,Seat::zombie,Seat::plant2,Seat::zombie2})if(seat_name(v)==s)return v;
    return std::nullopt;
}
std::string_view hit_name(HeroHit h) {
    switch(h){case HeroHit::normal:return "normal";case HeroHit::ash:return "ash";case HeroHit::swallow:return "swallow";case HeroHit::content:return "content";case HeroHit::lightning:return "lightning";case HeroHit::spring:return "spring";case HeroHit::grenade:return "grenade";case HeroHit::poison:return "poison";case HeroHit::hook:return "hook";case HeroHit::anchor:return "anchor";case HeroHit::chili:return "chili";case HeroHit::tentacle:return "tentacle";case HeroHit::black_armor:return "black_armor";}
    throw std::invalid_argument("invalid hero hit");
}
size_t HeroBudgetHash::operator()(const HeroBudgetKey& k) const noexcept {
    return std::hash<std::string>{}(k.attack) ^ (seat_index(k.seat)*17+size_t(k.hit)*71);
}
bool HeroCombat::contains(Seat s) const { return aliases[seat_index(s)]<heroes.size() && heroes[aliases[seat_index(s)]].has_value(); }
HeroState& HeroCombat::hero(Seat s) { if(!contains(s))throw std::invalid_argument("unknown hero");return *heroes[aliases[seat_index(s)]]; }
const HeroState& HeroCombat::hero(Seat s) const { return const_cast<HeroCombat*>(this)->hero(s); }

HeroContext::HeroContext(HeroCombat& w, HeroSelection selection) : world_(&w) {
    if(!w.contains(selection.target)||!w.contains(selection.owner))throw std::invalid_argument("unknown combat allegiance");
    if(w.active)copy_combat(w.hero(w.active->target).frame,w.globals);
    saved_=w.globals;previous_=w.active;w.active=std::move(selection);
    w.globals.overlay(w.hero(w.active->target).frame,false);
    w.globals.mode.set("正常模式");
    if(!w.globals.recovery.present())w.globals.recovery.set(0);
    if(!w.globals.hurt.present())w.globals.hurt.set(0);
    if(!w.globals.skin.present())w.globals.skin.set("普通戴夫");
}
void HeroContext::close() {
    if(!world_)return;
    auto& w=*world_;
    if(w.active->phase==CombatPhase::plants && w.globals.water_ice.or_missing(0)>saved_.water_ice.get())
        w.water_ice=std::max(w.water_ice,w.globals.water_ice.get());
    copy_combat(w.hero(w.active->target).frame,w.globals);
    w.globals=std::move(saved_);w.active=std::move(previous_);world_=nullptr;
    if(w.active)copy_combat(w.globals,w.hero(w.active->target).frame);
    w.sync_proxies();
}
HeroContext::~HeroContext() noexcept {
    // Valid typed states cannot fail here. Explicit close() exposes malformed
    // inputs to boundary callers; a failure during unwinding must not vanish.
    if(world_)try{close();}catch(...){std::terminate();}
}
std::shared_ptr<AttackSource> HeroCombat::source() const {
    if(!active)return {};
    if(active->source)return active->source;
    if(!source_index || *source_index<0)return {};
    const auto phase=active->phase;
    if(live_world) {
        const size_t index=size_t(*source_index);
        if(phase==CombatPhase::entities) {
            const auto list=live_world->runtime.entities.list();
            return index<list->size()?source_ref(list->at(index)):nullptr;
        }
        if(phase==CombatPhase::plants) {
            const auto& plants=*live_world->plant_roster;
            return index<plants.size()?source_ref(plants[index]):nullptr;
        }
        if(phase==CombatPhase::zombies) {
            const auto& roster=*live_world->targets;
            if(index>=roster.size())return {};
            return roster[index].is_hero()?proxy_source(roster[index].hero):source_ref(roster[index].unit);
        }
    }
    if(size_t(phase)>=phase_sources.size())return {};
    const auto& values=phase_sources.at(size_t(phase));
    return uint64_t(*source_index)<values.size()?values[size_t(*source_index)]:nullptr;
}
void HeroCombat::select_plant_seat(Seat seat) {
    if(team_of(seat)!=Seat::plant)throw std::invalid_argument("plant hero alias requires a plant seat");
    aliases[seat_index(Seat::plant)]=seat_index(seat);
    aliases[seat_index(Seat::plant2)]=seat_index(seat==Seat::plant?Seat::plant2:Seat::plant);
}
void HeroCombat::switch_plant_globals(Seat seat) {
    if(aliases[seat_index(Seat::plant)]==seat_index(seat))return;
    copy_combat(hero(Seat::plant).frame,globals);
    select_plant_seat(seat);globals.overlay(hero(Seat::plant).frame,false);
}
std::optional<Seat> HeroCombat::owner(const std::shared_ptr<AttackSource>& explicit_source) const {
    const auto s=explicit_source?explicit_source:source();
    if(s){if(s->charmed.present())return Seat::plant;const auto seat=known_seat(name(s->owner));if(seat&&contains(*seat))return seat;}
    return active?std::optional<Seat>(active->owner):std::nullopt;
}
std::string HeroCombat::source_id(const std::shared_ptr<AttackSource>& s) {
    if(!s)return "hero:"+std::string(active?seat_name(active->owner):"unknown");
    if(name(s->id).empty())s->id.set("native:"+std::to_string(++sequence));
    return s->id.get();
}
HeroBudgetKey HeroCombat::attack_key(Seat side, HeroHit kind) {
    auto s=source();std::optional<std::string> attack=active?active->attack:std::nullopt;
    if(!attack && s && s->instant_attack && !s->instant_attack->is_null())attack=s->instant_attack->hero_text();
    if(!attack) {
        const auto id=source_id(s);
        attack=(s&&s->projectile.present()?AttackIdentity::projectile(id):AttackIdentity::native(id,attack_tick())).hero_text();
    }
    return {side,kind,std::move(*attack)};
}
ChiliAttackKey HeroCombat::chili_attack_key() {
    auto s=source();if(!s)throw std::logic_error("chili attack without a source");
    const auto fallback=AttackIdentity::native(source_id(s),attack_tick());
    return {owner(),(s->instant_attack?*s->instant_attack:fallback).unit_key()};
}
double HeroCombat::cap_damage(HeroBudgetKey key, double amount, double cap) {
    const auto now=attack_tick();
    auto found=budget_index_.find(key);
    const double used=found==budget_index_.end()?0:budgets_[found->second].used;
    amount=std::min(amount,std::max(0.,cap-used));
    if(found==budget_index_.end()) {
        const auto index=budgets_.size();budgets_.push_back({std::move(key),now,used+amount});
        budget_index_.emplace(budgets_.back().key,index);
    } else budgets_[found->second]={std::move(key),now,used+amount};
    if(budgets_.size()>1024) {
        std::erase_if(budgets_,[&](const HeroBudget& b){return b.tick<now-2500;});
        if(budgets_.size()>2048) {
            std::stable_sort(budgets_.begin(),budgets_.end(),[](const HeroBudget& a,const HeroBudget& b){return a.tick<b.tick;});
            budgets_.erase(budgets_.begin(),budgets_.end()-1024);
        }
        budget_index_.clear();
        for(size_t i=0;i<budgets_.size();++i)budget_index_.emplace(budgets_[i].key,i);
    }
    return amount;
}
double HeroCombat::damage_factor(Seat side) const {
    const auto actual=hero(side).actual_seat.value_or(side);
    const auto& p=players[seat_index(actual)];
    if(!p)throw std::logic_error("hero damage factor without player");
    if(heroes.at(seat_index(actual)).value().frame.down.or_missing(0)>0) {
        if(team_of(actual)==Seat::plant && has(p->secrets,"secret:强健"))return .5;
        if(team_of(actual)==Seat::zombie && has(p->secrets,"zsecret:石更！"))return .75;
    }
    return 1.;
}
double HeroCombat::last_stand_amount(Seat side, double amount) {
    const auto i=seat_index(side);const auto& p=players[i];
    if(!p || team_of(side)!=Seat::zombie || !has(p->secrets,"zsecret:最后攻势"))return amount;
    const double hp=hero(side).frame.hp.or_missing(0);
    if(last_stand[i])return std::min(amount,std::max(0.,hp-1.));
    if(amount>=hp && !last_stand_used[i] && hp>0) {
        last_stand_used[i]=true;last_stand[i]=time+40.;last_stand_order.push_back(side);
        events.push_back(HeroDamageEvent{HeroDamageEvent::Type::last_stand_start,side,40.});
        return std::max(0.,hp-1.);
    }
    return amount;
}
void HeroCombat::hurt(double amount, bool pvp) {
    auto& g=globals;
    if(!pvp && name(g.mode)=="我是僵尸")return;
    if(g.down.get()==0 && name(g.skin)=="疯狂戴夫")presentation_.play_sound("戴夫疯狂");
    g.recovery.set(0);g.hp.set(g.hp.get()-amount);
    if(g.down.get()==0)g.down.set(1);
    g.hurt.set(1);
    const auto& pos=*g.position.get();
    const double count=4+amount*2;
    // Only the PvP wrapper rounds fractional damage's presentation count.
    if(!pvp && std::floor(count)!=count)throw std::invalid_argument("original blood count is not integral");
    presentation_.emit_particles("血",{pos.x,pos.y},int(std::ceil(count)));
}
void HeroCombat::on_damage(Seat side, double amount, HeroHit kind, const std::shared_ptr<AttackSource>& s) {
    side=hero(side).actual_seat.value_or(side);
    auto& h=hero(side);auto& p=players[seat_index(side)];
    if(!p)throw std::logic_error("hero damage event without player");
    if(amount>0){h.last_damage.set(double(tick)/250.);h.regen_progress.set(0);}
    if(team_of(side)==Seat::zombie && amount>0 && !(s&&flag(s->cattail)))p->marked_until=time+mark_seconds;
    auto o=owner(s);
    if(s&&s->seat&&players[seat_index(*s->seat)])o=s->seat;
    if(o&&players[seat_index(*o)]&&team_of(*o)!=team_of(side))players[seat_index(*o)]->hero_damage+=amount;
    events.push_back(HeroDamageEvent{HeroDamageEvent::Type::damage,side,amount,kind,s&&s->id.present()&&!s->id.is_null()?std::optional<std::string>(s->id.get()):std::nullopt});
}
double HeroCombat::damage(Seat side, double amount, HeroHit kind) {
    if(!active || amount<=0 || owner()==team_of(side))return 0.;
    auto s=source();if(s&&flag(s->no_hero_attack))return 0.;
    auto& a=hero(side).frame;if(a.hp.get()<=0)return 0.;
    if(kind==HeroHit::ash || kind==HeroHit::swallow) {
        auto key=attack_key(side,kind);double cap=hero(side).max_hp.or_missing(20.)*.4;
        if(s&&(name(s->plant)=="火爆辣椒" || s->zombie_name()=="辣椒僵尸" || name(s->projectile)=="火"))cap=std::min(cap,16.);
        amount=cap_damage(std::move(key),amount,cap);
    }
    if(damage_factors_enabled)amount*=damage_factor(side);
    if(last_stand_enabled)amount=last_stand_amount(side,amount);
    amount=std::min(amount,a.hp.get());if(amount<=0)return 0.;
    HeroFrame saved=globals;
    try {
        globals.overlay(a,true);if(!globals.skin.present())globals.skin.set("普通戴夫");
        hurt(amount,true);copy_hurt(a,globals);
    } catch(...) {globals=std::move(saved);throw;}
    globals=std::move(saved);
    if(active->target==side)copy_hurt(globals,a);
    if(damage_events_enabled)on_damage(side,amount,kind,source());
    sync_proxies();return amount;
}
std::optional<double> HeroCombat::player_damage(double amount) {
    if(!active){hurt(amount,false);return std::nullopt;}
    auto s=source();
    if(amount==1 && s && s->has_zombie_name()) {
        const auto v=name(s->variant);
        if(v=="黑普通僵尸"||v=="黑路障僵尸"||v=="黑铁桶僵尸"||v=="黑旗帜僵尸"||v=="黑撑杆僵尸"||v=="黑橄榄僵尸")amount=3.;
        else if(s->zombie_name()=="墓碑吞噬者僵尸"){  // PvP73.1: 3 above half HP, 6 at/below half
            amount=6.;if(const auto u=s->unit.lock())amount=u->body.hp<=u->max_hp.or_missing(300.)*.5?6.:3.;}
    }
    auto override=balanced_hero_amount(s.get(),active->target,globals);
    if(s&&flag(s->cattail)&&team_of(active->target)==Seat::zombie)override=2.;
    return damage(active->target,override.value_or(amount),damage_kind);
}
HeroProxyState& HeroCombat::proxy(Seat s) {
    if(!contains(s))throw std::invalid_argument("unknown hero proxy");
    if(!proxies[seat_index(s)]){
        // This factory is permanently the ordinary, normal-mode constructor
        // captured before card admission. Its temporary record is never in a
        // live unit list; restore constructor RNG even on failure.
        CombatZombie unit;
        const auto saved_rng=presentation_.rng.state();
        struct RestoreRng {PyRandom& rng;PyRandom::State state;~RestoreRng(){rng.set_state(state);}};
        {
            RestoreRng restore{presentation_.rng,saved_rng};
            auto position=*hero(s).frame.position.get();
            ZombieSpawnInput input;const auto& player=*globals.position.get();input.player={player.x,player.y};
            populate_original_zombie(presentation_,unit,"普通僵尸",position,1.,input);
        }
        auto retained=std::make_shared<HeroProxyState>();auto& candidate=*retained;
        static_cast<ZombieRecordFields&>(candidate)=std::move(static_cast<ZombieRecordFields&>(unit.body));
        candidate.native=std::move(unit.native);candidate.native.entry.set(500.);
        candidate.armor.clear();candidate.hand.clear();candidate.armor_hp=0.;candidate.hand_hp=0.;
        candidate.source.owner.set(std::string(seat_name(team_of(s))));candidate.source.id.set("hero:"+std::string(seat_name(s)));
        sync_proxy_state(candidate,hero(s));
        candidate.identity=presentation_.identities.assign();
        proxies[seat_index(s)]=std::move(retained);
    }
    sync_proxy(s);return *proxies[seat_index(s)];
}
void HeroCombat::sync_proxy_state(HeroProxyState& p,const HeroState& h) {
    p.ice=h.ice.present()?h.ice:Field<double>(0.);p.butter=h.butter.present()?h.butter:Field<double>(0.);p.stun=h.stun.present()?h.stun:Field<double>(0.);
    p.hp=std::max(0.,h.frame.hp.get());p.position=h.frame.position.get();p.facing=h.frame.facing.or_missing(1.);
}
void HeroCombat::sync_proxy(Seat s) {sync_proxy_state(*proxies[seat_index(s)],hero(s));}
void HeroCombat::sync_proxies(){for(size_t i=0;i<proxies.size();++i)if(proxies[i])sync_proxy(Seat(i));}
void HeroCombat::context_effects(Seat target,Seat owner,CombatPhase phase) {
    if(!contains(target)||!contains(owner))throw std::invalid_argument("unknown combat allegiance");
    if(phase==CombatPhase::plants)throw std::invalid_argument("plant context needs water side effect");
    if(active)copy_combat(hero(active->target).frame,globals);
    auto& frame=hero(target).frame;
#define FILL(n) if(!frame.n.present()&&globals.n.present())frame.n=globals.n;
    PVZ72_HERO_COMBAT(FILL)
#undef FILL
    if(!frame.recovery.present())frame.recovery.set(0.);if(!frame.hurt.present())frame.hurt.set(0.);
    if(active)copy_combat(globals,hero(active->target).frame);
    sync_proxies();
}
void HeroCombat::write_proxy_hp(Seat s,double value) {
    if(!proxies[seat_index(s)])proxy(s);
    const double old=proxies[seat_index(s)]->hp;
    if(value<old){damage(s,old-value,value<=-1024?HeroHit::swallow:damage_kind);sync_proxy(s);}
}
void HeroCombat::write_proxy_ash(Seat s){damage(s,40.,HeroHit::ash);if(!proxies[seat_index(s)])proxy(s);else sync_proxy(s);}
void HeroCombat::write_proxy_status(Seat s,HeroStatus status,double value) {
    if(!proxies[seat_index(s)])proxy(s);
    if(owner()==s)return;
    auto& h=hero(s);auto& p=*proxies[seat_index(s)];value=std::max(0.,value);
    switch(status) {
    case HeroStatus::ice:h.ice.set(value);p.ice.set(value);break;
    case HeroStatus::butter:h.butter.set(value);p.butter.set(value);break;
    case HeroStatus::stun:h.stun.set(value);p.stun.set(value);break;
    }
}
void HeroCombat::write_proxy_conversion(Seat side,HeroConversion) {
    // HeroProxy.__setitem__ intentionally discards every conversion value,
    // including direct transforms, armor replacement and instant despawn.
    if(!proxies.at(seat_index(side)))proxy(side);
}
void HeroCombat::step_last_stand() {
    for(const auto side:last_stand_order) {
        const auto i=seat_index(side);auto& a=heroes.at(i).value().frame;
        if(time>=*last_stand[i]) {
            last_stand[i].reset();a.hp.set(0);
            if(!players[i])throw std::logic_error("last stand without player");
            players[i]->hp=0;events.push_back(HeroDamageEvent{HeroDamageEvent::Type::last_stand_end,side});
        } else {a.hp.set(std::max(1.,a.hp.or_missing(0)));a.down.set(0);a.recovery.set(0);}
    }
    std::erase_if(last_stand_order,[&](Seat s){return !last_stand[seat_index(s)];});
}

std::string_view projectile_fire_color(const AttackSource& s,const HeroFrame& g) {
    const auto projectile=name(s.projectile);auto color=name(s.fire_color);
    if(color.empty())color=name(s.zombie_fire);
    if(color.empty()&&projectile=="蓝火豆")color="blue";
    if(color.empty()&&projectile=="火豆")color=secret(g,"蓝火")?"blue":"fire";
    return color;
}
std::optional<double> balanced_hero_amount(const AttackSource* s, Seat side, const HeroFrame& g) {
    if(!s)return std::nullopt;
    const auto projectile=name(s->projectile),content=name(s->content);
    const auto plant=name(s->plant.present()?s->plant:s->plant_kind);
    const bool zombie=team_of(side)==Seat::zombie;const auto color=projectile_fire_color(*s,g);
    if(!color.empty()&&flag(s->melon_splash)) {
        if(zombie&&content=="原始豌豆射手")return color=="blue"?4.:3.;
        return color=="blue"?2.:1.5;
    }
    if(!zombie)return std::nullopt;
    if(content=="甜椒投手")return 10.;
    if(content=="原始豌豆射手")return color=="blue"?16.:!color.empty()?12.:8.;
    if(plant=="胆小菇"||plant=="胆小鬼")return 2.5;
    if(plant=="海蘑菇"||(plant=="小喷菇"&&content!="忧郁藤蔓"))return 2.5;
    if(plant=="大喷菇"||plant=="雷蘑菇")return 5.;
    if(projectile=="豌豆"||projectile=="冰豆"||projectile=="火豆"||projectile=="蓝火豆"||projectile=="僵尸豌豆")return color=="blue"?8.:!color.empty()?6.:4.;
    if(projectile=="西瓜"||projectile=="冰瓜")return flag(s->melon_splash)?4.:16.;
    if(plant=="寒冰菇")return 8.;
    if(plant=="地刺"||plant=="地刺王"||plant=="钢地刺")return 2.5;
    if(projectile=="玉米粒"||projectile=="玉米")return 2.;
    if(projectile=="黄油"||projectile=="卷心菜")return 8.;
    return std::nullopt;
}
std::optional<double> HeroCombat::source_amount(Seat side) const {
    auto s=source();auto override=balanced_hero_amount(s.get(),side,globals);if(override)return override;
    const bool zombie=team_of(side)==Seat::zombie;
    if(zombie&&s&&name(s->plant)=="忧郁蘑菇")return 4.;
    if(!s||!s->projectile.present())return std::nullopt;
    const auto n=name(s->projectile),p=name(s->plant_kind),content=name(s->content);
    if(zombie) {
        if(p=="小喷菇"&&content!="忧郁藤蔓")return 2.5;
        if(p=="海蘑菇")return 2.5;
        if(n=="星星")return 6.;
        if(n=="尖刺"&&flag(s->cattail))return 2.;
        if(content=="甜椒投手")return flag(s->melon_splash)?5.:15.;
        if(content=="原始豌豆射手") {
            if(!flag(s->melon_splash))return 15.;
            const bool blue=n=="蓝火豆"||(n=="火豆"&&secret(globals,"蓝火"));return blue?6.:3.;
        }
    }
    if(flag(s->melon_splash))return 2.;
    if(n=="火豆"&&secret(globals,"蓝火"))return 16.;
    if(n=="卷心菜"||n=="火豆")return 12.;
    if(n=="蓝火豆"||n=="西瓜"||n=="冰瓜"||n=="窝瓜x")return 16.;
    if(n=="星星")return 30.;
    return std::nullopt;
}
} // namespace pvz::typed72
