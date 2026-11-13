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
    // Only the shooting phase owns this read-only position cache. Special
    // callbacks invalidate it before the next ordinary shooter is considered.
    void begin_phase(){phase_=true;invalidate_phase();}
    void end_phase(){phase_=false;invalidate_phase();}
    void invalidate_phase()const{plant_data_=nullptr;zombie_data_=nullptr;enemy_data_=nullptr;}
    mutable uint64_t aim_queries=0,aim_candidates=0,aim_full_scan=0;
private:
    TypedBattleState& world_;
    const CollisionCatalog& catalog_;
    bool phase_=false;
    struct Search {double x;size_t index;};
    mutable std::vector<Search> plant_search_,zombie_search_;
    mutable const PlantRef* plant_data_=nullptr;
    mutable const CombatTarget* zombie_data_=nullptr;
    mutable size_t plant_count_=0,zombie_count_=0;
    mutable TargetRoster enemy_view_;
    mutable const CombatTarget* enemy_data_=nullptr;
    mutable size_t enemy_count_=0;
    void prepare_plants()const;
    void prepare_zombies(const TargetRoster&)const;
    const TargetRoster& enemy_view(const ZombieRef&)const;
    std::optional<Point> player_point()const;
    void consider_zombies(const TargetRoster&,const ZombieRef&,Point center,bool charmed_targets,
                          std::optional<NativeAimTarget>& best,std::optional<double>& score)const;
};
} // namespace pvz::typed72
