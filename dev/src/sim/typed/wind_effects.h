#pragma once
#include "sim/typed/plant_zombie_target.h"
#include "sim/typed/wind_state.h"
namespace pvz::typed72 {
class WindServices {
public:
    virtual ~WindServices()=default;
    // Resolve this numeric index against the currently exposed native roster.
    virtual void wind_surface(size_t index,double direction,double damage)=0;
};
class WindEffects {
public:
    WindEffects(TypedBattleState& w,WindServices& s,const CollisionCatalog& c,double width)
        :world_(w),services_(s),catalog_(c),width_(width){}
    uint64_t blows=0;
    void raw_wind(const ZombieRef&,double strength=1.);
    void wind(const ZombieRef&,double strength=1.);
    void raw_update(const ZombieRef&,const PlantZombieConfig&);
    void update(const ZombieRef&,const PlantZombieConfig&);
    void before_plants();
    void after_plants();
    void after_zombies();
    const std::array<std::optional<double>,4>& plant_baselines()const noexcept{return plant_baselines_;}
private:
    TypedBattleState& world_;
    WindServices& services_;
    const CollisionCatalog& catalog_;
    double width_;
    std::array<std::optional<double>,4> plant_baselines_;
    std::shared_ptr<TargetRoster> surface_roster_;
    std::vector<size_t> surface_indices_;
    void radius_wind(const ZombieRef&,double);
    void mapped_surface(size_t,double,double);
    ZombieRecordFields& fields(const CombatTarget&)const;
    std::shared_ptr<Motion> position(const CombatTarget&)const;
    double hero_acceleration()const;
    double hero_limit()const;
};
} // namespace pvz::typed72
