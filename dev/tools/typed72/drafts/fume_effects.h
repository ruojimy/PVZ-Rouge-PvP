#pragma once
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class FumeCallbacks {
public:
    virtual ~FumeCallbacks()=default;
    virtual void zombie_damage(size_t index,double direction,double amount)=0;
    virtual void player_damage(double amount)=0;
    virtual void clear_plant(Cell)=0;
};
class FumeEffects {
public:
    FumeEffects(TypedBattleState& w,FumeCallbacks& callbacks,const CollisionCatalog& catalog)
        :world_(w),callbacks_(callbacks),catalog_(catalog),aim_(w,catalog){}
    uint64_t attack_count=0;
    bool thunder(const ZombieRef&)const;
    bool has_metal(const CombatTarget&)const;
    bool stun(const CombatTarget&,Point);
    bool within(Point,Point,double radius_tiles)const;
    bool ray(Point origin,double angle,Point point,double radius,double length_tiles)const;
    NativeAim pick(const ZombieRef&,const PlantZombieConfig&)const;
    bool damage_plant(const PlantRef&,double);
    bool damage_player(double direction=1.);
    bool damage_zombie(size_t index,CombatTarget,double amount,double direction);
    void bubbles(Point,double angle,const PlantZombieConfig&,bool blue=false);
    void update_bubbles(std::optional<double> now={});
    int64_t fire_frames(const PlantZombieConfig&)const;
    int64_t visual_tick(const PlantZombieConfig&)const;
    int64_t shoot_tick(const ZombieRef&,const PlantZombieConfig&)const;
    size_t raw_line(const ZombieRef&,Point,double angle,const PlantZombieConfig&);
    size_t line(const ZombieRef&,Point,double angle,const PlantZombieConfig&);
    bool fire_animation(const ZombieRef&,const PlantZombieConfig&);
    void raw_update(const ZombieRef&,const PlantZombieConfig&);
    void update(const ZombieRef&,const PlantZombieConfig&);
private:
    TypedBattleState& world_;
    FumeCallbacks& callbacks_;
    const CollisionCatalog& catalog_;
    PlantZombieTargeting aim_;
    ZombieRecordFields& body(const CombatTarget&)const;
    bool i_zombie()const;
    void splat(Point);
};
} // namespace pvz::typed72
