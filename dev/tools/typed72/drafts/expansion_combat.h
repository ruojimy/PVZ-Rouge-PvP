#pragma once
#include "sim/typed/expansion_combat_state.h"
#include "sim/typed/plant_aim.h"

namespace pvz::typed72 {
class ExpansionCombatServices {
public:
    virtual ~ExpansionCombatServices()=default;
    virtual HitResult expansion_inner_damage(size_t,double,double)=0;
    virtual void expansion_outer_damage(size_t,double,double)=0;
    virtual bool expansion_barrel_active(const ZombieRef&)const=0;
    virtual void expansion_correct_barrel(const ZombieRef&)=0;
    virtual void black_armor_event(const std::string&,Point)=0;
    virtual void expansion_armor_clear()=0;
    virtual void expansion_armor_gate(const ZombieRef&)=0;
    virtual void expansion_restore_art()=0;
    virtual bool expansion_has_art(const std::string&)const=0;
    virtual void expansion_alias_one(const std::string&,const std::string&)=0;
    virtual void expansion_draw_pole(Point)=0;
};
class ExpansionCombat {
public:
    ExpansionCombat(TypedBattleState& world,const TargetSight& published,PeaHybrid& hybrid,
                    const bool& drawing,ExpansionCombatServices& services)
        :world_(world),published_(published),hybrid_(hybrid),drawing_(drawing),services_(services){}
    bool pea_hybrid=false,paralysis_secret=false,silence_secret=false;
    ZombieRef last_zombie;
    void configure_locked_secrets();
    void configure(const ZombieRef&,const ExpansionVariantSetup&);
    static std::optional<std::string> worn_black_armor(const ZombieRef&);
    void armor_drop(const ZombieRef&);
    void black_armor_blast(const ZombieRef&,const std::string&);
    HitResult ordinary(size_t,double,double);
    void after_projectile(const std::shared_ptr<AttackSource>& captured_source,const PlantRef& captured_plant,
                          size_t first,std::optional<int64_t> magnet_target);
    void apply_paralysis(const ZombieRef&);
    void apply_paralysis(const CombatTarget&);
    void paralysis_recovery(const ZombieRef&);
    void paralysis_recovery(const CombatTarget&);
    void charge(const ZombieRef&);
    void finish_zombie();
    void zombie_gate(const ZombieRef&);
    void source_gate(const PlantRef&,const EntityRef& entity = {});
    void alias_art(const std::string&,const std::string&);
private:
    TypedBattleState& world_;const TargetSight& published_;PeaHybrid& hybrid_;
    const bool& drawing_;ExpansionCombatServices& services_;
    bool solid(Point)const;
    ExpansionCombatState& state(const CombatTarget&)const;
    ZombieRecordFields& body(const CombatTarget&)const;
    ZombieNativeState& native(const CombatTarget&)const;
    void stun(const CombatTarget&,double);
};
}
