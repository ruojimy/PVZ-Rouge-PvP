#include "sim/typed/sourced_context.h"
namespace pvz::typed72 {
std::shared_ptr<AttackSource> SourcedContext::resolve_source(TypedBattleState& w,std::shared_ptr<AttackSource> source) {
    if(!source)source=w.heroes.source();if(!source)throw std::invalid_argument("missing PvP sourced context");return source;
}
Seat SourcedContext::source_owner(const AttackSource& s){return s.charmed.present()?Seat::plant:s.owner.present()?parse_seat(s.owner.get()):Seat::zombie;}
SourcedContext::SourcedContext(TypedBattleState& w,std::shared_ptr<AttackSource> source,CombatPhase phase,SourcedCall call)
    :world_(w),source_(resolve_source(w,std::move(source))),call_(call) {
    // This intentionally differs from HeroCombat::owner(): a missing owner
    // defaults to zombie, whereas an explicit invalid/None owner is rejected.
    owner_=source_owner(*source_);
    const auto target=call==SourcedCall::player_hit?owner_:owner_==Seat::plant?Seat::zombie:Seat::plant;
    if(call==SourcedCall::spawn){const auto entities=w.runtime.entities.list();previous_entities_.reserve(entities->size());for(const auto& e:*entities)previous_entities_.insert(e->identity.value);}
    context_.emplace(w.heroes,HeroSelection{target,owner_,phase,source_,{}});
    const auto& launch=w.heroes.globals.chili_launch;was_launching_=launch.present()&&!launch.is_null()&&launch.get()!=0.;
}
void SourcedContext::finish() {
    if(finished_)throw std::logic_error("sourced context already finished");
    auto& heroes=world_.heroes;const auto& launch=heroes.globals.chili_launch;
    if(call_==SourcedCall::player_hit&&!was_launching_&&(launch.present()?launch.get():0.)>0.) {
        // Python evaluates dict.get's default eagerly, even when an explicit
        // attack token exists. Preserve that observable source-ID allocation.
        auto fallback=AttackIdentity::native(heroes.source_id(source_),heroes.attack_tick());
        heroes.hero(owner_).launch_attack=source_->instant_attack?*source_->instant_attack:std::move(fallback);
    }
    if(call_==SourcedCall::spawn)for(const auto& e:*world_.runtime.entities.list())
        if(!previous_entities_.contains(e->identity.value))heroes.tag_entity(source_ref(e),&e->motion.get(),e->flight,owner_,source_);
    context_->close();finished_=true;
}
} // namespace pvz::typed72
