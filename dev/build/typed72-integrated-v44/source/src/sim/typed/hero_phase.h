#pragma once
#include "sim/typed/hero_physics.h"
#include <span>

namespace pvz::typed72 {
struct RallyPoints {
    std::optional<Point> shared;
    std::array<std::optional<Point>,4> by_seat;
    const std::optional<Point>& for_owner(MatchMode mode,std::optional<Seat> seat)const{
        return mode==MatchMode::duo?by_seat.at(seat_index(seat.value_or(Seat::zombie))):shared;
    }
};
// Seat order comes from the match. Physics and ability passes are separated
// by world, plant and zombie updates in the native battle driver.
class HeroPhase {
public:
    HeroPhase(TypedBattleState& world,HeroPhysics& physics,NativeTracking& tracking,const TargetSight& map,const RallyPoints& rally)
        :world_(world),physics_(physics),tracking_(tracking),map_(map),rally_(rally){}
    void initialize(Seat,Point,double rule_hp,const std::vector<std::string>& deck,std::vector<std::string> native_secret_names);
    void advance(std::span<const Seat>);
    void effects(std::span<const Seat>,double now,double tail_activation_seconds);
private:
    TypedBattleState& world_;
    HeroPhysics& physics_;
    NativeTracking& tracking_;
    const TargetSight& map_;
    const RallyPoints& rally_;
    void rally_rise(HeroState&);
    bool float_body(HeroState&)const;
    void tag_births(Seat,HeroState&,size_t);
};
} // namespace pvz::typed72
