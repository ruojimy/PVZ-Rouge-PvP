#include "sim/typed/death_chain.h"
#include <algorithm>
namespace pvz::typed72 {
namespace {
double number(const Field<double>& f,double fallback=0.){return f.present()&&!f.is_null()?f.get():fallback;}
bool flag(const Field<bool>& f){return f.present()&&!f.is_null()&&f.get();}
std::string_view name(const Field<std::string>& f){return f.present()&&!f.is_null()?f.get():std::string_view{};}
}
NativeDeathChain::NativeDeathChain(TypedBattleState& w,PlantLifecycle& plants,DeathServices& services,const CollisionCatalog& catalog)
    :patch(w.runtime,w.heroes,*this),damage(w.heroes,w.protection,patch),doom(w,damage,plants,services,catalog),
     graves(w,plants),chili(w,damage,plants,services,*this),world_(w),services_(services){patch.bind(damage);}
int64_t NativeDeathChain::zombie_index(const ZombieRef& unit) {
    const auto& roster=*world_.targets;const auto i=std::find(roster.begin(),roster.end(),CombatTarget::zombie(unit));
    if(i==roster.end())throw std::out_of_range("raw ash target missing from current roster");return i-roster.begin();
}
ZombieRef NativeDeathChain::resolve(const DeathTarget& target)const {
    if(const auto* u=std::get_if<ZombieRef>(&target))return *u;
    const auto n=std::get<int64_t>(target);if(n<0||uint64_t(n)>=world_.targets->size())return {};
    // Hero proxies have no plant-zombie death kind; they never enter these
    // original plant-zombie selectors or mobile death/reward loops.
    return world_.targets->at(size_t(n)).unit;
}
bool NativeDeathChain::plant_zombie_deaths(const DeathTarget& target) {
    const auto* unit=std::get_if<ZombieRef>(&target);
    if(sourced_fastpath&&unit&&*unit) {
        const auto kind=name((*unit)->patch.plant_name);
        if(kind!="辣椒僵尸"&&kind!="毁灭菇僵尸"&&kind!="墓碑吞噬者僵尸"){context_effects(source_ref(*unit));return false;}
    }
    SourcedContext context(world_,unit&&*unit?source_ref(*unit):std::shared_ptr<AttackSource>{},CombatPhase::zombies);
    bool triggered=false;
    // Numeric targets resolve anew for EACH selector. A chili callback may
    // replace the list before the doom/grave selector executes.
    try{triggered=patch.trigger_chili(resolve(target))||triggered;}catch(const std::exception&){}
    try{triggered=patch.trigger_doom(resolve(target))||triggered;}catch(const std::exception&){}
    try{triggered=patch.trigger_grave(resolve(target))||triggered;}catch(const std::exception&){}
    context.finish();return triggered;
}
bool NativeDeathChain::chili_fire_row(const ZombieRef& u,bool friendly) {
    SourcedContext context(world_,source_ref(u),CombatPhase::zombies,SourcedCall::spawn);
    const bool result=chili.spawn_fire(u,friendly);context.finish();return result;
}
bool NativeDeathChain::doom_explosion(const ZombieRef& u) {
    SourcedContext context(world_,source_ref(u),CombatPhase::zombies,SourcedCall::spawn);
    const bool result=doom.explode(u);context.finish();return result;
}
void NativeDeathChain::armor_broken(const ZombieRef& u,ArmorSlot s,const std::string& kind,double maximum){services_.armor_broken(u,s,kind,maximum);}
std::optional<int> NativeDeathChain::row_hint(const CombatTarget& t,bool force) {
    auto source=t.is_hero()?world_.heroes.proxy_source(t.hero):source_ref(t.unit);
    if(sourced_fastpath){context_effects(source);return chili.row_hint(t,force);}
    SourcedContext context(world_,std::move(source),CombatPhase::zombies);
    const auto result=chili.row_hint(t,force);context.finish();return result;
}
void NativeDeathChain::enemy_scan(const EntityRef& e,FlameBox box,double scale) {
    SourcedContext context(world_,source_ref(e),CombatPhase::entities);
    chili.enemy_scan(e,box,scale);player_hit(e,box,scale);context.finish();
}
void NativeDeathChain::player_hit(const EntityRef& e,FlameBox box,double scale) {
    SourcedContext context(world_,source_ref(e),CombatPhase::entities,SourcedCall::player_hit);
    chili.player_hit(e,box,scale);context.finish();
}
void NativeDeathChain::hit_zombies(const EntityRef& e,FlameBox box,double scale,bool charmed,const std::optional<FireRows>& rows) {
    SourcedContext context(world_,source_ref(e),CombatPhase::entities);
    chili.hit_zombies(e,box,scale,charmed,rows);context.finish();
}
bool NativeDeathChain::auto_explode(const ZombieRef& unit,std::optional<double> now) {
    if(sourced_fastpath&&name(unit->patch.plant_name)!="毁灭菇僵尸"){context_effects(source_ref(unit));return false;}
    SourcedContext context(world_,source_ref(unit),CombatPhase::zombies);bool result=false;auto& u=*unit;auto& p=u.patch;
    if(p.plant_name.present()&&!p.plant_name.is_null()&&p.plant_name.get()=="毁灭菇僵尸"&&!flag(p.doom_exploded)&&
       !u.body.dead.present()&&!u.body.ash.present()&&u.body.hp>0.) {
        const double clock=now.value_or(world_.native_time);double age=number(p.doom_life_ticks),elapsed=0.;
        if(p.doom_life_time.present()&&!p.doom_life_time.is_null()){elapsed=clock-p.doom_life_time.get();if(elapsed<0.||elapsed>10.)elapsed=0.;}
        // This patch's age clock is 60 Hz even though native simulation steps
        // run at 250 Hz. Its literal DOOM_ZOMBIE_NATIVE_FPS is authoritative.
        if(elapsed>0.)age+=elapsed*60.;p.doom_life_ticks.set(age);p.doom_life_time.set(clock);
        if(age>=9500.){u.body.hp=0.;result=patch.trigger_doom(unit);}
    }
    context.finish();return result;
}
void NativeDeathChain::context_effects(const std::shared_ptr<AttackSource>& source) {
    const auto owner=SourcedContext::source_owner(*SourcedContext::resolve_source(world_,source));
    world_.heroes.context_effects(owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::zombies);
}
} // namespace pvz::typed72
