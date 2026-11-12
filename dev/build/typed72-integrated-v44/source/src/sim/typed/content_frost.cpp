#include "sim/typed/content_frost.h"
namespace pvz::typed72 {
bool ContentFrost::contains(const CombatTarget& target)const{return std::find(pending.begin(),pending.end(),target)!=pending.end();}
double ContentFrost::ice(const CombatTarget& target)const {
    const auto& body=target.is_hero()?static_cast<const ZombieRecordFields&>(world_.heroes.cached_proxy(target.hero)):
        static_cast<const ZombieRecordFields&>(target.unit->body);
    return body.ice.or_missing(0.);
}
void ContentFrost::freeze(const CombatTarget& target,double minimum) {
    const double value=std::max(ice(target),minimum);
    if(target.is_hero())world_.heroes.write_proxy_status(target.hero,HeroStatus::ice,value);
    else target.unit->body.ice.set(value);
}
void ContentFrost::apply() {
    auto source=std::make_shared<AttackSource>();source->owner.set("plant");
    HeroContext scope(world_.heroes,{Seat::zombie,Seat::plant,CombatPhase::status,source,{}});
    // Pending references survive a roster replacement and preserve insertion
    // order, including repeated references to the same frozen body.
    for(size_t i=0;i<pending.size();++i)freeze(pending[i],2250.);
    pending.clear();
}
} // namespace pvz::typed72
