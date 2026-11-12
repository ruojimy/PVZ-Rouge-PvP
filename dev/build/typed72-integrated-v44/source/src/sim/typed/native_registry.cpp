#include "sim/typed/native_registry.h"
#include "sim/typed/targets.h"
#include <array>
#include <iterator>
#include <stdexcept>
namespace pvz::typed72 {
std::span<const Seat> seats_for(MatchMode mode) {
    static constexpr std::array duel{Seat::plant,Seat::zombie};
    static constexpr std::array duo{Seat::plant,Seat::zombie,Seat::plant2,Seat::zombie2};
    static constexpr std::array pve{Seat::plant};
    static constexpr std::array coop{Seat::plant,Seat::plant2};
    switch(mode){case MatchMode::duel:return duel;case MatchMode::duo:return duo;case MatchMode::pve:return pve;case MatchMode::coop:return coop;}
    throw std::invalid_argument("unknown typed match mode");
}
void NativeObjectRegistry::set(std::string key,NativeObject object) {
    if(!std::visit([](const auto& p){return bool(p);},object))throw std::invalid_argument("null native object");
    if(const auto i=by_key_.find(key);i!=by_key_.end()){i->second->object=std::move(object);return;}
    ordered_.push_back({std::move(key),std::move(object)});auto entry=std::prev(ordered_.end());
    try{by_key_.emplace(entry->key,entry);}catch(...){ordered_.pop_back();throw;}
}
bool NativeObjectRegistry::erase(const std::string& key) {
    const auto i=by_key_.find(key);if(i==by_key_.end())return false;
    ordered_.erase(i->second);by_key_.erase(i);return true;
}
std::optional<NativeObject> NativeObjectRegistry::get(const std::string& key)const {
    const auto i=by_key_.find(key);if(i==by_key_.end())return {};return i->second->object;
}
std::vector<CombatTarget> collect_native_extras(const NativeObjectRegistry& records,HeroCombat& heroes,MatchMode mode) {
    std::vector<CombatTarget> result;result.reserve(records.size()+2);
    for(const auto& entry:records.entries())if(const auto* unit=std::get_if<std::shared_ptr<CombatZombie>>(&entry.object)) {
        const auto& u=**unit;
        if((u.protection.grave||u.orphan_barrel)&&u.body.hp>0.)result.push_back(CombatTarget::zombie(*unit));
    }
    // PvE/coop have a dormant zombie avatar for faction bookkeeping, but no
    // zombie Dave target. Duel/duo retain participating fallen heroes too.
    for(const Seat seat:seats_for(mode))if(team_of(seat)==Seat::zombie){heroes.proxy(seat);result.push_back(CombatTarget::player(seat));}
    return result;
}
TargetRoster TypedBattleState::omitted_targets(){return collect_native_extras(native_objects,heroes,mode);}
} // namespace pvz::typed72
