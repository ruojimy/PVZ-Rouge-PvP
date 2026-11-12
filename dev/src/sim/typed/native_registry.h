#pragma once
#include "sim/typed/allegiance.h"
#include <list>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <unordered_map>
#include <variant>
#include <vector>
namespace pvz::typed72 {
struct CombatPlant;
struct CombatZombie;
struct CombatTarget;
class HeroCombat;
using NativeObject=std::variant<std::shared_ptr<CombatPlant>,std::shared_ptr<CombatZombie>>;
enum class MatchMode { duel,duo,pve,coop };
std::span<const Seat> seats_for(MatchMode);

// Ordered keyed references to the authoritative bodies. Replacing a key keeps
// its order; erase followed by insert appends, exactly as the native dict does.
// Different keys may name the same body. full_targets performs its own dedupe.
class NativeObjectRegistry {
public:
    struct Entry { std::string key;NativeObject object; };
    NativeObjectRegistry()=default;
    NativeObjectRegistry(const NativeObjectRegistry&)=delete;
    NativeObjectRegistry& operator=(const NativeObjectRegistry&)=delete;
    void set(std::string key,NativeObject);
    bool erase(const std::string& key);
    std::optional<NativeObject> get(const std::string& key)const;
    size_t size()const noexcept{return ordered_.size();}
    const std::list<Entry>& entries()const noexcept{return ordered_;}
private:
    std::list<Entry> ordered_;
    std::unordered_map<std::string,std::list<Entry>::iterator> by_key_;
};
std::vector<CombatTarget> collect_native_extras(const NativeObjectRegistry&,HeroCombat&,MatchMode);
} // namespace pvz::typed72
