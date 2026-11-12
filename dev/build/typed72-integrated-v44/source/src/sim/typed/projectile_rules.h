#pragma once
#include "sim/typed/targets.h"
namespace pvz::typed72 {
struct Ellipse {Point center;double rx=0.,ry=0.;};
struct PlantHeadGeometry {
    double head_x=.08,head_y=1.35,duck_head_x=.08,duck_head_y=1.35,head_scale=.68;
    double fire_frames=24.;
    bool fumeshroom=false;
};
// Immutable typed values resolved from the actual battle catalog/atlas at
// construction. No dynamic dictionaries are consulted by collision code.
struct CollisionCatalog {
    std::unordered_map<std::string,double> unit_scale,flyer_image_height;
    std::unordered_map<std::string,PlantHeadGeometry> plant_heads;
    double default_fire_frames=24.;
};
double unit_scale_factor(const AttackSource&,const CollisionCatalog&);
double wrap_delta(double from,double to,double width);
bool segment_hits_ellipse(Point a,Point b,const Ellipse&);
std::optional<Ellipse> plant_zombie_head(const CombatZombie&,double tile,const CollisionCatalog&);
Point native_plant_zombie_head_center(const CombatZombie&,double tile,const CollisionCatalog&);
Point content_target_point(const CombatZombie&,double tile,const CollisionCatalog&);
bool flying_target_contact(const CombatZombie&,Point start,Point delta,double tile,double width,const CollisionCatalog&);
bool head_overlaps_area(const CombatZombie&,Point center,double rx,double ry,double tile,double width,const CollisionCatalog&);

class ProjectileImpactDamage {
public:
    virtual ~ProjectileImpactDamage()=default;
    virtual void damage_zombie(size_t,double direction,double amount)=0;
};
class ProjectileRules {
public:
    ProjectileRules(TypedBattleState& world,TargetDamage& damage,const CollisionCatalog& catalog,double width,double splash_damage)
        :events(world.runtime.events),world_(world),damage_(damage),catalog_(catalog),width_(width),melon_splash_damage_(splash_damage){}
    // Actual NativeProjectiles.expired, including basketball's mobile-unit
    // sweep and synchronous typed damage. No alternate old-backend path.
    bool expired(const EntityRef&);
    void cull_flight();
    void impact(const EntityRef&,ProjectileImpactDamage* installed=nullptr);
    std::vector<BattleEvent>& events;
private:
    TypedBattleState& world_;
    TargetDamage& damage_;
    const CollisionCatalog& catalog_;
    double width_;
    double melon_splash_damage_;
    bool basketball(const EntityRef&,Point previous);
};
} // namespace pvz::typed72
