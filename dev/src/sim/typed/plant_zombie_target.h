#pragma once
#include "sim/typed/plant_zombie_catalog.h"
#include "sim/typed/sourced_context.h"
namespace pvz::typed72 {
struct NativeAimTarget {
    // monostate is the selected native player globals, deliberately resolved
    // again on use. Unit targets retain both object and captured list index.
    std::variant<PlantRef,CombatTarget,std::monostate> object;
    size_t index=0;
    Point captured_point;
    double direction=1.,angle=0.;
};
struct NativeAim {std::optional<NativeAimTarget> target;Point center;};
TargetRoster plant_zombie_enemy_view(TypedBattleState&,const ZombieRef&);
double native_direction_angle(double direction);
double native_direction_angle_diff(double angle,double direction);
bool native_angle_in_direction(double angle,double direction,double limit=90.);
std::pair<double,double> sync_native_head_angle(CombatZombie&);
class PlantZombieTargeting {
public:
    PlantZombieTargeting(TypedBattleState& world,const CollisionCatalog& catalog):world_(world),catalog_(catalog){}
    Point zombie_point(const CombatTarget&)const;
    std::optional<Point> plant_aim(const CombatPlant&,Point center)const;
    std::optional<NativeAimTarget> pick(const ZombieRef&)const;
    std::optional<Point> point(const NativeAimTarget&,Point center)const;
    NativeAim raw_update(const ZombieRef&);
    NativeAim update(const ZombieRef&);
private:
    TypedBattleState& world_;
    const CollisionCatalog& catalog_;
    std::optional<Point> player_point()const;
    void consider_zombies(const TargetRoster&,const ZombieRef&,Point center,bool charmed_targets,
                          std::optional<NativeAimTarget>& best,std::optional<double>& score)const;
};
} // namespace pvz::typed72
