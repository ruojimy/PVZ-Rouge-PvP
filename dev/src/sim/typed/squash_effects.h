#pragma once
#include "sim/typed/ballistics.h"
#include "sim/typed/plant_zombie_target.h"
namespace pvz::typed72 {
class SquashCallbacks : public ProjectileImpactDamage {
public:
    virtual ~SquashCallbacks()=default;
    virtual void add_entity(std::string,double,Motion)=0;
    virtual void clear_plant(Cell)=0;
    virtual void ash_zombie(size_t index)=0;
    virtual void player_damage(double amount)=0;
};
struct SquashResolved {std::optional<std::string> kind;std::optional<NativeAimTarget> target;std::optional<Point> point;};
class SquashEffects {
public:
    SquashEffects(TypedBattleState& w,SquashCallbacks& cb,const CollisionCatalog& c):world_(w),callbacks_(cb),catalog_(c),aim_(w,c),ballistics(w){}
    NativeBallistics ballistics;
    uint64_t patches=0,attacks=0,damages=0;
    static std::optional<std::pair<double,double>> candidate(Point origin,Point target,double direction,double scale,double size=2.);
    NativeAim pick(const ZombieRef&)const;
    std::optional<SquashTargetRecord> record(const std::optional<NativeAimTarget>&)const;
    BallisticTarget ballistic(const NativeAimTarget&);
    Point velocity(const NativeAimTarget&);
    bool apply_solution(const EntityRef&,const BallisticTarget&,Point velocity,double speed,bool late=false);
    void patch_entity(const EntityRef&);
    void finish_entities();
    bool raw_spawn(const ZombieRef&,const std::optional<NativeAimTarget>&,Point origin,const PlantZombieConfig&);
    bool spawn(const ZombieRef&,const std::optional<NativeAimTarget>&,Point origin,const PlantZombieConfig&);
    void raw_update(const ZombieRef&,const PlantZombieConfig&);
    void update(const ZombieRef&,const PlantZombieConfig&);
    SquashResolved resolve(const Field<SquashTargetRecord>&)const;
    void kill_plant(const PlantRef&);
    void damage_charmed(size_t,CombatTarget,double direction);
    bool damage_player(const EntityRef&,double impact_x,double direction);
    void raw_hit(const EntityRef&,const Field<SquashTargetRecord>&,double impact_x);
    void hit(const EntityRef&,const Field<SquashTargetRecord>&,double impact_x);
    bool enemy(const EntityRef&)const;
    bool pending()const;
    void update_entities();
    bool splash_secret(bool enabled,std::optional<int64_t> target_index,double width);
private:
    TypedBattleState& world_;
    SquashCallbacks& callbacks_;
    const CollisionCatalog& catalog_;
    PlantZombieTargeting aim_;
    bool i_zombie()const;
    void update_roster();
};
} // namespace pvz::typed72
