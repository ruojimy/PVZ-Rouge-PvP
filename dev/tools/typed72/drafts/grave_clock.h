#pragma once
#include "sim/typed/economy.h"

namespace pvz::typed72 {
struct GraveIdleRules {
    double idle_seconds=20.,doze_seconds=20.,sleep_rate=.5,scarecrow_radius=6.;
    std::string scarecrow;
};
enum class GraveWakeResult {success,wrong_team,invalid_id,missing,nonproducer};
class GraveClock {
public:
    GraveClock(TypedBattleState& world,EconomyState& economy,const GraveIdleRules& rules)
        :world_(world),economy_(economy),rules_(rules){}
    double level(const CombatZombie&)const;
    bool drowsy(const CombatZombie&)const;
    void wake(const ZombieRef&,std::string cause);
    GraveWakeResult wake_input(Seat,std::optional<std::string> id);
    double idle(const ZombieRef&,double factor,std::span<const Seat> present);
    void advance(std::span<const ZombieRef> graves,std::span<const Seat> present,double production_multiplier);
private:
    TypedBattleState& world_;
    EconomyState& economy_;
    const GraveIdleRules& rules_;
    bool guarded(const CombatZombie&)const;
    bool touched(const CombatZombie&,std::span<const Seat>)const;
};
} // namespace pvz::typed72
