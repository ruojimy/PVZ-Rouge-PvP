#pragma once
#include "sim/typed/content_combat_state.h"
#include "sim/typed/content_frost.h"
#include "sim/typed/content_zombie_bindings.h"
#include "sim/typed/native_status.h"
#include "sim/typed/damage_patch.h"
#include "sim/typed/bonus_projectiles.h"
#include "sim/typed/chili_effects.h"
namespace pvz::typed72 {
// This is the next installed layer, not an alternate backend. The production
// patch composer supplies its actual expansion/death/protection chain here.
class ContentDamageLower {
public:
    virtual ~ContentDamageLower()=default;
    virtual HitResult hit(size_t,double,double)=0;
    virtual HitResult surface_hit(size_t,double,double)=0;
    virtual HitResult ash(size_t)=0;
    virtual void knock(size_t,double)=0;
    virtual std::optional<double> player_damage(double)=0;
};
class ContentTargetDamageLower final : public ContentDamageLower {
public:
    ContentTargetDamageLower(TypedBattleState& world,TargetDamage& damage,DamagePatch& patch)
        :world_(world),damage_(damage),patch_(patch){}
    HitResult hit(size_t i,double f,double a)override{return damage_.ordinary(world_.targets->at(i),f,a);}
    HitResult surface_hit(size_t i,double f,double a)override{return damage_.surface(world_.targets->at(i),f,a);}
    HitResult ash(size_t i)override{return damage_.ash(world_.targets->at(i));}
    std::optional<double> player_damage(double amount)override{return world_.heroes.player_damage(amount);}
    void knock(size_t,double)override;
private:
    TypedBattleState& world_;TargetDamage& damage_;DamagePatch& patch_;
};
struct ContentHitOrigin {
    EntityRef head_entity;
    ZombieRef current,other;
    bool reciprocal_bite=false;
};
class NativeContentDamage final : public ContentUnitDamage,public ProjectileImpactDamage,public BonusImpactServices,public ChiliImpactDispatch {
public:
    NativeContentDamage(TypedBattleState& world,ContentCombatState& state,ContentDamageLower& lower,
        NativeBarrels& barrels,ContentZombieControllers& zombies,NativeStatus& status,ContentFrost& frost,
        ProjectileRules& projectiles,const CollisionCatalog& collision,const bool& gas_secret)
        :world_(world),state_(state),lower_(lower),barrels_(barrels),zombies_(zombies),status_(status),frost_(frost),
         projectiles_(projectiles),collision_(collision),gas_secret_(gas_secret){}
    HitResult hit(size_t,double,double,const ContentHitOrigin& = {});
    HitResult surface_hit(size_t,double,double,const ContentHitOrigin& = {});
    HitResult freeze_hit(size_t);
    void knockback(size_t,double);
    std::optional<double> player_damage(double,const ZombieRef& source={},bool native_bite=false);
    HitResult head_impact(const EntityRef&,size_t,double,double,bool surface);
    void primal_knockback(size_t,double,const EntityRef&);
    double primal_damage(const EntityRef&)const;
    uint64_t primal_knock_targets=0;
    double primal_knock_velocity=0.;
    bool allows_hit(const CombatTarget&,const std::shared_ptr<AttackSource>&)const;
    static bool content_projectile(const EntityRef&);
    static bool multi_blue_direct(const EntityRef&);
    void gas_hit(const std::shared_ptr<AttackSource>&,const CombatTarget&);
    // The explicit head call-site replaces Python caller-frame inspection.
    void head_damage(const EntityRef& e,size_t i,double f,double a,bool surface)override;
    void ordinary(size_t i,double f,double a)override{hit(i,f,a);}
    void surface(size_t i,double f,double a)override{surface_hit(i,f,a);}
    void damage_zombie(size_t i,double f,double a)override{hit(i,f,a);}
    void bonus_damage(size_t i,double f,double a)override{hit(i,f,a);}
    void chili_ash(size_t index)override{freeze_hit(index);}
    bool chili_player_launch(const EntityRef& entity)const override{return !cold(entity);}
    bool chili_hit_one(ChiliEffects& chili,const EntityRef& entity,size_t index,const CombatTarget& target,
        std::vector<ChiliKey>& hits,FlameBox box,double scale,const std::optional<FireRows>& rows)override {
        return cold_flame(entity,target,[&]{return chili.raw_hit_one(entity,index,target,hits,box,scale,rows);});
    }
    template<class F> bool cold_flame(const EntityRef& entity,const CombatTarget& target,F&& original) {
        const double previous=frost_.ice(target);const auto owner=world_.heroes.owner(source_ref(entity)).value();
        bool result;
        {HeroContext scope(world_.heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::entities,source_ref(entity),{}});result=original();}
        if(result && cold(entity)) {
            HeroContext scope(world_.heroes,{owner==Seat::plant?Seat::zombie:Seat::plant,owner,CombatPhase::entities,source_ref(entity),{}});
            frost_.freeze(target,std::max(previous,frost_.contains(target)?2250.:0.));
        }
        return result;
    }
    static bool cold(const EntityRef& e){return e->source.content.present()&&!e->source.content.is_null()&&e->source.content.get()=="寒冰辣椒";}
private:
    TypedBattleState& world_;ContentCombatState& state_;ContentDamageLower& lower_;NativeBarrels& barrels_;
    ContentZombieControllers& zombies_;NativeStatus& status_;ContentFrost& frost_;ProjectileRules& projectiles_;
    const CollisionCatalog& collision_;const bool& gas_secret_;
    ZombieRecordFields& body(const CombatTarget&)const;
    Motion& motion(const CombatTarget&)const;
    std::shared_ptr<AttackSource> source(const CombatTarget&)const;
    bool anchored(const CombatTarget&)const;
};
} // namespace pvz::typed72
