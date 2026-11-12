#pragma once
#include "sim/typed/resources.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct EconomyRules {
    double day_interval=0.,day_amount=0.,sky_amount=0.,sun_lifetime=0.;
};
struct ProductionRules {
    double rest_seconds=0.,ramp_seconds=0.,rest_bonus=0.,multiplier=1.;
    bool deathmatch=false;
};
struct EconomyState {
    int64_t previous_tick=0;
    double sky_progress=0.,sky_interval=0.,subsidy_phase=0.;
    bool night=false,subsidy=false;
    std::vector<Point> death_points;
    std::unordered_map<std::string,double> grave_progress;
};
class Economy {
public:
    Economy(TypedBattleState& world,WorldRegionState& native,Resources& resources,
            EconomyState& state,const TargetSight& map,const std::vector<std::string>& producers)
        :world_(world),native_(native),resources_(resources),state_(state),map_(map),producers_(producers){}
    void advance(std::span<const Seat> present,double room_elapsed,const EconomyRules&);
    Seat sun_owner(NativeSun&,std::span<const Seat> present)const;
    std::optional<double> death_sun_amount(const NativeSun&);
    void plant_production(const ProductionRules&);
private:
    TypedBattleState& world_;
    WorldRegionState& native_;
    Resources& resources_;
    EconomyState& state_;
    const TargetSight& map_;
    const std::vector<std::string>& producers_;
    double day_payments(int64_t previous,int64_t now,double interval);
    void loose_suns(std::span<const Seat>,bool multi_plant);
    void sky(double elapsed,const EconomyRules&,bool multi_plant);
    void graves();
};
} // namespace pvz::typed72
