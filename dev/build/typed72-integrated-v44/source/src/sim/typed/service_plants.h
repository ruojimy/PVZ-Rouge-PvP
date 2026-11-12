#pragma once
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class ServicePlantCallbacks {
public:
    virtual ~ServicePlantCallbacks()=default;
    virtual void add_entity(std::string,double,Motion)=0;
    // Source uses __pvz_sb_add_entity_original here; components keep the forwarded default.
    virtual void add_original_entity(std::string n,double f,Motion m){add_entity(std::move(n),f,m);}
};
struct MagnetTarget {CombatTarget target;Point point;bool handheld=false;bool imp=false;};
class ServicePlants {
public:
    // NativeBattle overrides __pvz_sb_GOLD_MAGNET_BUCKET_HP with balance.GOLD_MAGNET_BUCKET_HP.
    double bucket_hp=500.;
    // NativeBattle._install_imp_armor_hooks (PvP only): riding-imp recipients and the gift_bucket wrapper.
    bool imp_armor_hooks=false;
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
    // _riding_imp_candidate: the imp on a carrier's back as a separate recipient.
    std::optional<MagnetTarget> riding_imp(Point center,double tiles,bool armed);
    bool absorb_imp(const CombatTarget&,Point target,Point center);
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
