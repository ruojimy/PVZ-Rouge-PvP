#pragma once
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class LanternServices {
public:
    virtual ~LanternServices()=default;
    virtual void add_entity(std::string,double facing,Motion)=0;
};
class LanternEffects {
public:
    LanternEffects(TypedBattleState& w,LanternServices& services,const CollisionCatalog& catalog)
        :world_(w),services_(services),catalog_(catalog),aim_(w,catalog){}
    uint64_t zombie_heals=0,native_charmed_heals=0;
    void track_max_hp();
    bool heal_zombie(const CombatTarget&,double);
    bool heal_plant(const PlantRef&,double);
    int multiplier()const;
    bool in_range(Point center,Point point,double tiles=3.)const;
    void effects(Point,int64_t count=1);
    size_t heal_targets(const ZombieRef&,Point);
    void raw_update(const ZombieRef&,const PlantZombieConfig&);
    void update(const ZombieRef&,const PlantZombieConfig&);
    void native_charmed_healing();
private:
    TypedBattleState& world_;
    LanternServices& services_;
    const CollisionCatalog& catalog_;
    PlantZombieTargeting aim_;
};
} // namespace pvz::typed72
