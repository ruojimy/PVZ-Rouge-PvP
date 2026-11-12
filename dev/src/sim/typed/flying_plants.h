#pragma once
#include "sim/typed/content_queries.h"
#include "sim/typed/native_tracking.h"

namespace pvz::typed72 {
struct FlyingSweepEvent {
    Field<std::string> source;
    double angle=0.,facing=1.;
};
class FlyingPlantServices {
public:
    virtual ~FlyingPlantServices()=default;
    virtual void flying_sweep(const FlyingSweepEvent&)=0;
    virtual void draw_flying_shot(const EntityRef&)=0;
};
class FlyingPlants {
public:
    FlyingPlants(TypedBattleState& world,ContentQueries& queries,ContentTargets& targets,
                 const TargetSight& published,const CollisionCatalog& collision,FlyingPlantServices& services)
        :world_(world),queries_(queries),targets_(targets),published_(published),collision_(collision),services_(services){}
    bool configure(const PlantRef&,std::string_view name);
    std::vector<ContentTarget> nearby(const PlantRef&,double radius);
    bool clear_line(Point origin,Point target)const;
    std::optional<ContentTarget> turnip_target(const PlantRef&);
    void advance(const PlantRef&);
    EntityRef fire(const PlantRef&,double angle);
    void before_tick();
    double wall_contact(Point origin,Point delta)const;
    double contact_reach(const ContentTarget&,Point)const;
    void projectiles();
private:
    TypedBattleState& world_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    const TargetSight& published_;
    const CollisionCatalog& collision_;
    FlyingPlantServices& services_;
    bool solid(Point)const;
};
} // namespace pvz::typed72
