#pragma once
#include "sim/typed/content_zombies.h"
#include "sim/typed/cart_lifecycle.h"
#include "sim/typed/content_zombies56.h"
#include "sim/typed/content_zombies70.h"
#include "sim/typed/september_zombies.h"
#include "sim/typed/native_barrels.h"
namespace pvz::typed72 {
struct ContentZombieCombatRules {
    std::vector<std::string> black_variants,black_hero_bite_variants;
};
class ContentZombiePresentation {
public:
    virtual ~ContentZombiePresentation()=default;
    virtual void alias_art(const std::string&,const std::string&)=0;
    virtual void tint_poison(const ZombieRef&)=0;
    virtual double image_height(const std::string&)const=0;
    virtual void stun_star(Point,Point)=0;
    virtual void draw_content_zombie(const ZombieRef&)=0;
};
// Production controller wiring. Every gate/finish branch calls a concrete
// typed service; only rendering and catalog construction remain boundaries.
class ContentZombieBindings final : public ContentZombieControllers {
public:
    ContentZombieBindings(TypedBattleState& world,CartLifecycle& carts,SeptemberZombies& september,
        ContentZombies56& zombies56,ContentZombies70& zombies70,NativeBarrels& barrels,const TargetSight& published,
        const CollisionCatalog& collision,const ContentZombieCombatRules& rules,const bool& charm_secret,
        ContentZombiePresentation& presentation)
        :world_(world),carts_(carts),september_(september),zombies56_(zombies56),zombies70_(zombies70),barrels_(barrels),
         published_(published),collision_(collision),rules_(rules),charm_secret_(charm_secret),presentation_(presentation){}
    void cart_before(const ZombieRef& unit)override{carts_.before(unit);}
    void cart_animate(const ZombieRef& unit,bool active,bool fired)override{carts_.animate(unit,active,fired);}
    void september_gate(const ZombieRef& unit)override{september_.gate(unit);}
    void september_wave_chase(const ZombieRef& unit)override{september_.wave_chase(unit);}
    void september_finish(const ZombieRef& unit)override{september_.finish(unit);}
    void zombies56_gate(const ZombieRef& unit)override{zombies56_.gate(unit);}
    void zombies56_finish(const ZombieRef& unit)override{zombies56_.finish(unit);}
    void zombies70_gate(const ZombieRef& unit)override{zombies70_.gate(unit);}
    void barrel_correct_pair(const ZombieRef& unit)override{barrels_.correct_pair(unit);}
    void barrel_detach(const ZombieRef& unit,double hp)override{barrels_.detach(unit,hp);}
    void barrel_break(const ZombieRef& unit)override{barrels_.break_barrel(unit);}
    void barrel_move(const ZombieRef& unit,double factor)override{barrels_.move(unit,factor);}
    void barrel_contact(const ZombieRef& unit,double factor)override{barrels_.contact(unit,factor);}
    bool solid(Point)const override;
    double bite_damage(const ZombieRef&,const ContentTarget&)override;
    double movement_factor(const ZombieRef&)const override;
    void alias_art(const std::string& first,const std::string& second)override{presentation_.alias_art(first,second);}
    void tint_poison(const ZombieRef& unit)override{presentation_.tint_poison(unit);}
    double image_height(const std::string& name)const override{return presentation_.image_height(name);}
    double unit_scale(const ZombieRef&)const override;
    void stun_star(Point point,Point dimensions)override{presentation_.stun_star(point,dimensions);}
    void draw_content_zombie(const ZombieRef& unit)override{presentation_.draw_content_zombie(unit);}
private:
    TypedBattleState& world_;
    CartLifecycle& carts_;
    SeptemberZombies& september_;
    ContentZombies56& zombies56_;
    ContentZombies70& zombies70_;
    NativeBarrels& barrels_;
    const TargetSight& published_;
    const CollisionCatalog& collision_;
    const ContentZombieCombatRules& rules_;
    const bool& charm_secret_;
    ContentZombiePresentation& presentation_;
};
} // namespace pvz::typed72
