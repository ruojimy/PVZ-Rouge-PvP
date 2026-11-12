#pragma once
#include "sim/typed/content_queries.h"
#include "sim/typed/world_regions.h"

namespace pvz::typed72 {
struct SeptemberPlantEvent {
    enum class Kind {bloom,ghost_activated,ghost_exploded} kind;
    Field<std::string> source;
    double sun_amount=0.;
};
struct GhostBlast {int64_t tick;Point point;};
class SeptemberPlantServices {
public:
    virtual ~SeptemberPlantServices()=default;
    virtual void september_event(const SeptemberPlantEvent&)=0;
};
class SeptemberPlants {
public:
    SeptemberPlants(TypedBattleState& world,WorldRegionState& resources,ContentQueries& queries,
                    ContentTargets& targets,const CollisionCatalog& collision,SeptemberPlantServices& services)
        :world_(world),resources_(resources),queries_(queries),targets_(targets),collision_(collision),services_(services){}
    bool configure(const PlantRef&,std::string_view name);
    void advance(const PlantRef&);
    bool inside(const PlantRef&,const ContentTarget&,double horizontal,double vertical)const;
    void attack(const PlantRef&,double amount,double horizontal,double vertical,double hero_amount,
                HeroHit kind=HeroHit::content);
    std::vector<GhostBlast> effects;
private:
    TypedBattleState& world_;
    WorldRegionState& resources_;
    ContentQueries& queries_;
    ContentTargets& targets_;
    const CollisionCatalog& collision_;
    SeptemberPlantServices& services_;
};
} // namespace pvz::typed72
