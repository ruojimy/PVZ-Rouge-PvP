#pragma once
#include "sim/typed/hero.h"
namespace pvz::typed72 {
// Locked battle choices and deployment-only accounting. Resources, hero HP,
// secrets and cooldowns retain their existing owners.
struct ColdPlayerDeployment {
    std::vector<std::string> deck;
    std::optional<std::string> last_copy_card;
    double spent=0.;
};
struct ColdDeploymentState {
    std::array<ColdPlayerDeployment,4> players;
    std::vector<std::string> bans;
    std::string map_source;
    std::optional<Seat> acting_seat;
    std::optional<int64_t> scripted_wave;
    bool ranked=false;
    Field<double> spike_cost;
};
} // namespace pvz::typed72
