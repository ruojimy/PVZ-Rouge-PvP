// Concrete 1.5.0.1 damage wrappers and death selection. Direct native call
// conditions are explicit values; no stack inspection or dynamic value ABI.
#pragma once
#include "sim/typed/targets.h"
#include <variant>

namespace pvz::typed72 {
using DeathTarget=std::variant<ZombieRef,int64_t>;
struct NativeDamageOrigin {
    struct EntityContact {bool enemy_squash=false,blue_tripea=false,tracking_present=false;};
    std::optional<EntityContact> entity;
    // The two native charm-bite call sites, already identified by the driver.
    ZombieRef current_charmed,other;
    bool charm_bite_site=false,native_horizontal_chili=false;
};

// Required synchronous game services. In particular the death effects must
// run before the damage wrapper returns: recording a deferred effect would
// change chain reactions. NativeDeathChain composes the typed implementations
// with source contexts; the complete battle scheduler remains required.
class DamagePatchEffects {
public:
    virtual ~DamagePatchEffects()=default;
    virtual int64_t zombie_index(const ZombieRef&)=0;
    virtual bool plant_zombie_deaths(const DeathTarget&)=0;
    virtual void chili_row_hint(const ZombieRef&,bool force)=0;
    virtual bool chili_fire_row(const ZombieRef&,bool friendly)=0;
    virtual bool doom_explosion(const ZombieRef&)=0;
    virtual bool grave_remnant(const ZombieRef&)=0;
    virtual bool gravebuster_plant(const ZombieRef&)=0;
    virtual void armor_broken(const ZombieRef&,ArmorSlot,const std::string&,double)=0;
};
struct DamagePatchCounters {
    uint64_t charm_bite=0,blue_damage=0,blue_surface=0,squash_skipped=0,chili_skipped=0,pumpkin_sound=0;
};
class DamagePatch final : public RawDamageChain {
public:
    // Native surface/ash bodies call the installed ordinary-damage entry.
    // A typed outer wrapper may intercept that call; it must delegate to
    // TargetDamage explicitly, preserving the active protection packet.
    class NestedOrdinary {
    public:
        virtual ~NestedOrdinary()=default;
        virtual HitResult ordinary(const ZombieRef&,double,double)=0;
    };
    DamagePatch(CombatRuntime& runtime,HeroCombat& heroes,DamagePatchEffects& effects)
        :runtime_(runtime),heroes_(heroes),effects_(effects){}
    void bind(TargetDamage& damage){if(dispatch_&&dispatch_!=&damage)throw std::logic_error("damage patch already bound");dispatch_=&damage;}
    void bind_nested_ordinary(NestedOrdinary& wrapper){if(nested_&&nested_!=&wrapper)throw std::logic_error("nested damage already bound");nested_=&wrapper;}
    std::vector<std::string> bosses;
    DamagePatchCounters counters;
    HitResult ordinary(const ZombieRef&,double,double)override;
    HitResult surface(const ZombieRef&,double,double)override;
    HitResult ash(const ZombieRef&)override;
    void armor_broken(const ZombieRef& u,ArmorSlot s,const std::string& kind,double hp)override{effects_.armor_broken(u,s,kind,hp);}
    HitResult ordinary_from(const ZombieRef&,double,double,const NativeDamageOrigin&);
    HitResult surface_from(const ZombieRef&,double,double,const NativeDamageOrigin&);
    HitResult ash_from(const ZombieRef&,const NativeDamageOrigin&);
    void knockback(const ZombieRef&,double);
    bool trigger_deaths(const ZombieRef&);
    bool trigger_chili(const ZombieRef&);
    bool trigger_doom(const ZombieRef&);
    bool trigger_grave(const ZombieRef&);
    static void remember_max_hp(CombatZombie&);
private:
    CombatRuntime& runtime_;
    HeroCombat& heroes_;
    DamagePatchEffects& effects_;
    TargetDamage* dispatch_=nullptr;
    NestedOrdinary* nested_=nullptr;
    TargetDamage& dispatch(){if(!dispatch_)throw std::logic_error("unbound typed damage patch");return *dispatch_;}
    HitResult nested_ordinary(const ZombieRef& u,double f,double a){return nested_?nested_->ordinary(u,f,a):dispatch().ordinary(CombatTarget::zombie(u),f,a);}
    double bite_amount(const ZombieRef&,double,const NativeDamageOrigin&) const;
    void pumpkin_sound(const ZombieRef&,double);
};
} // namespace pvz::typed72
