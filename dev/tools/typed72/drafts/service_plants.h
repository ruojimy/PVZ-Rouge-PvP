#pragma once
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class ServicePlantCallbacks {
public:
    virtual ~ServicePlantCallbacks()=default;
    virtual void add_entity(std::string,double,Motion)=0;
};
struct MagnetTarget {CombatTarget target;Point point;bool handheld=false;};
class ServicePlants {
public:
    ServicePlants(TypedBattleState& w,ServicePlantCallbacks& callbacks,const CollisionCatalog& catalog)
        :world_(w),callbacks_(callbacks),catalog_(catalog),aim_(w,catalog){}
    uint64_t umbrella_triggers=0,magnet_gifts=0,magnet_absorbs=0;
    void animate(const ZombieRef&,const PlantZombieConfig&,double spread=35.);
    bool live(const CombatTarget&)const;
    bool head_armor(const CombatTarget&)const;
    size_t reflect(const ZombieRef&,Point,double tiles);
    size_t bounce(Point,double tiles);
    size_t knock_zombies(const ZombieRef&,Point,double tiles);
    size_t knock_player(Point,double tiles);
    void raw_umbrella(const ZombieRef&,const PlantZombieConfig&);
    void umbrella(const ZombieRef&,const PlantZombieConfig&);
    void raw_pvp_umbrella(const ZombieRef&,const PlantZombieConfig&,bool sourced=false);
    std::optional<MagnetTarget> bucket_target(const ZombieRef&,Point,double tiles);
    std::optional<MagnetTarget> absorb_target(const ZombieRef&,Point,double tiles);
    bool gift(const CombatTarget&,Point);
    bool absorb(const CombatTarget&,Point target,Point center,bool handheld);
    EntityRef attract(std::string,Point start,Point end);
    void raw_magnet(const ZombieRef&,const PlantZombieConfig&);
    void magnet(const ZombieRef&,const PlantZombieConfig&);
private:
    TypedBattleState& world_;
    ServicePlantCallbacks& callbacks_;
    const CollisionCatalog& catalog_;
    PlantZombieTargeting aim_;
    ZombieRecordFields& body(const CombatTarget&)const;
    bool in_range(Point,Point,double)const;
};
} // namespace pvz::typed72
