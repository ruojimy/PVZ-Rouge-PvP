#pragma once
#include "sim/typed/content_target.h"
#include "sim/typed/native_status_state.h"

namespace pvz::typed72 {
class NativeStatusServices {
public:
    virtual ~NativeStatusServices()=default;
    virtual void poison_damage(const Field<std::string>& entity,double amount,int level)=0;
    virtual void break_poisoned_barrel(const ZombieRef&)=0;
    virtual void detach_poisoned_barrel(const ZombieRef&)=0;
};

class NativeStatus {
public:
    NativeStatus(TypedBattleState& world,NativeStatusServices& services)
        :world_(world),services_(services){}
    void apply(const ContentTarget&,int level,double duration=4.,Seat owner=Seat::plant);
    void tick(std::span<const Seat> avatar_order);
    static std::shared_ptr<PoisonLayers> layers(PoisonState&);
    static void summarize(PoisonSlot&,const std::shared_ptr<PoisonState>&);
private:
    struct Subject {
        ZombieRef unit;
        HeroState* avatar=nullptr;
        PoisonSlot& slot()const{return unit?unit->poison.poison:avatar->poison;}
        double hp()const{return unit?unit->body.hp:avatar->frame.hp.or_missing(0.);}
        std::shared_ptr<AttackSource> source()const{return unit?source_ref(unit):avatar->avatar_source;}
    };
    TypedBattleState& world_;
    NativeStatusServices& services_;
    void advance(const Subject&,double now);
    void pulse(const Subject&,const PoisonLayer&,int level);
};
} // namespace pvz::typed72
