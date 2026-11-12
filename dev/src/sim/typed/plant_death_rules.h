#pragma once
#include "sim/typed/economy.h"

namespace pvz::typed72 {
struct PlantZombieConversion {
    std::string name;
    Point position;
    double facing=1.;
    Seat seat=Seat::zombie;
};
struct PlantDeathRules {
    bool zombie_secrets_enabled=false;
    bool nuclear_secret=false;
    // Lock-time holders are sorted by their original seat names. The map
    // contains only forms admitted by the authoritative card catalog.
    std::vector<Seat> brain_holders,conversion_holders;
    std::unordered_map<std::string,std::string> conversion_forms;
    double brains_per_kill=15.;
};
struct PlantDeathState {
    std::vector<PlantZombieConversion> conversions;
};
class PlantDeathPolicy {
public:
    PlantDeathPolicy(TypedBattleState& world,Resources& resources,EconomyState& economy,
                    PlantDeathState& state,const PlantDeathRules& rules)
        :world_(world),resources_(resources),economy_(economy),state_(state),rules_(rules){}
    void killed(const PlantRef&);
    bool supplement(size_t plant_index);
    bool second_doom_ash(int64_t target_index);
private:
    TypedBattleState& world_;
    Resources& resources_;
    EconomyState& economy_;
    PlantDeathState& state_;
    const PlantDeathRules& rules_;
};
} // namespace pvz::typed72
